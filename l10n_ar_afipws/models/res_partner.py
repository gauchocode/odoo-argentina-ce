##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging
import html

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    mipyme_required = fields.Boolean(
        string="Must credit invoice",
    )
    mipyme_from_amount = fields.Float(
        string="Credit invoice from amount",
    )
    last_update_census = fields.Date(string="Last update census")


    def unescape_dict(self, data):
        if isinstance(data, dict):
            return {k: self.unescape_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.unescape_dict(v) for v in data]
        elif isinstance(data, str):
            return html.unescape(data)
        else:
            return data
    # Separo esto para poder heredar de otros
    # modulos y extender los datos
    def parse_census_vals(self, padron):
        """
        Procesa los datos del padrón AFIP y devuelve un diccionario
        de valores para actualizar el res.partner.
        """
        for attr, value in padron.__dict__.items():
            if isinstance(value, (dict, list, str)):
                setattr(padron, attr, self.unescape_dict(value))


        # Normalización del valor de IVA
        imp_iva = padron.imp_iva
        if imp_iva == "S":
            imp_iva = "AC"
        elif imp_iva == "N":
            imp_iva = "NI"

        # Generación inicial de valores
        vals = {
            "name": padron.denominacion,
            # Descomentar estos si se necesitan como campos adicionales:
            # 'name': padron.tipo_persona,
            # 'name': padron.tipo_doc,
            # 'name': padron.dni,
            "estado_padron": padron.estado,
            "street": padron.direccion,
            "city": padron.localidad,
            "zip": padron.cod_postal,
            "actividades_padron": self.env["afip.activity"].search(
                [("code", "in", padron.actividades)]
            ).ids,
            "impuestos_padron": self.env["afip.tax"].search(
                [("code", "in", padron.impuestos)]
            ).ids,
            "imp_iva_padron": imp_iva,
            # 'imp_ganancias_padron': padron.imp_ganancias,  # Aún no funcional
            "monotributo_padron": padron.monotributo,
            "actividad_monotributo_padron": padron.actividad_monotributo,
            "empleador_padron": True if padron.empleador == "S" else False,
            "integrante_soc_padron": padron.integrante_soc,
            "last_update_padron": fields.Date.today(),
        }

        # --- Provincia y Estado ---
        _logger.debug("provincia: %s", padron.provincia)
        _logger.info(padron.data)

        
        if padron.provincia:
            caba_codes = ["C", "CABA", "ABA"]
            state = None

            if not padron.localidad:
                # Si no hay localidad, se asume CABA
                state = self.env["res.country.state"].search(
                    [("code", "in", caba_codes), ("country_id.code", "=", "AR")], limit=1
                )
            else:
                # Provincia enviada por AFIP (puede venir sin acentos)
                provincia_afip = padron.data.get("domicilioFiscal", {}).get("descripcionProvincia", "").strip()

                # Provincias que necesitan corrección de acento
                # Persona del futuro, te preguntaras porque esta bestialidad?
                # La respuesta es simple, las provincias estan guardadas con tilde en odoo
                # Pero afip en su divina sabiduria las devuelve sin tilde

                if provincia_afip == "CORDOBA":
                    provincia_afip = "Córdoba"
                elif provincia_afip == "ENTRE RIOS":
                    provincia_afip = "Entre Ríos"
                elif provincia_afip == "NEUQUEN":
                    provincia_afip = "Neuquén"
                elif provincia_afip == "RIO NEGRO":
                    provincia_afip = "Río Negro"
                elif provincia_afip == "TUCUMAN":
                    provincia_afip = "Tucumán"

                _logger.info("provincia_afip: %s", provincia_afip)

                # Búsqueda en Odoo con el nombre corregido
                state = self.env["res.country.state"].search(
                    [
                        ("name", "ilike", provincia_afip),
                        ("code", "not in", caba_codes),
                        ("country_id.code", "=", "AR"),
                    ],
                    limit=1,
                )

            if state:
                vals["state_id"] = state.id


        _logger.info("impuesto y monotributo: %s , %s", imp_iva, padron.monotributo)
        # --- Responsabilidad ante AFIP ---
        if imp_iva == "NI" and padron.monotributo == "S":
            # Responsable Monotributo
            vals["l10n_ar_afip_responsibility_type_id"] = self.env.ref("l10n_ar.res_RM").id

        elif imp_iva == "NI" and padron.monotributo == "N":
            # Consumidor Final
            vals["l10n_ar_afip_responsibility_type_id"] = self.env.ref("l10n_ar.res_CF").id

        elif imp_iva == "AC":
            # Responsable Inscripto
            vals["l10n_ar_afip_responsibility_type_id"] = self.env.ref("l10n_ar.res_IVARI").id

        elif imp_iva == "EX":
            # Exento
            vals["l10n_ar_afip_responsibility_type_id"] = self.env.ref("l10n_ar.res_IVAE").id
        
        elif imp_iva == "NA":
            # Exento
            vals["l10n_ar_afip_responsibility_type_id"] = self.env.ref("l10n_ar.res_IVA_NO_ALC").id
            
        else:
            _logger.info(
                "We couldn't infer the AFIP responsability from padron, you must set it manually."
            )

        # --- Impuesto a las ganancias (comentado por ahora) ---
        # ganancias_inscripto = [10, 11]
        # ganancias_exento = [12]
        # if set(ganancias_inscripto) & set(padron.impuestos):
        #     vals["imp_ganancias_padron"] = "AC"
        # elif set(ganancias_exento) & set(padron.impuestos):
        #     vals["imp_ganancias_padron"] = "EX"
        # elif padron.monotributo == "S":
        #     vals["imp_ganancias_padron"] = "NC"
        # else:
        #     _logger.info(
        #         "We couldn't get impuesto a las ganancias from padron, you must set it manually."
        #     )

        return vals


    def get_data_from_padron_afip(self):
        self.ensure_one()
        cuit = self.ensure_vat()

        # GET COMPANY
        # if there is certificate for user company, use that one, if not
        # use the company for the first certificate found
        company = self.env.user.company_id
        env_type = company._get_environment_type()
        try:
            certificate = company.get_key_and_certificate(
                company._get_environment_type()
            )
        except Exception:
            certificate = self.env["afipws.certificate"].search(
                [
                    ("alias_id.type", "=", env_type),
                    ("state", "=", "confirmed"),
                ],
                limit=1,
            )
            if not certificate:
                raise UserError(_("Not confirmed certificate found on database"))
            company = certificate.alias_id.company_id

        # consultamos a5 ya que extiende a4 y tiene validez de constancia
        padron = company.get_connection("ws_sr_constancia_inscripcion").connect()
        error_msg = _(
            "No pudimos actualizar desde padron afip al partner %s (%s).\n"
            "Recomendamos verificar manualmente en la página de AFIP.\n"
            "Obtuvimos este error: %s"
        )
        try:
            padron.Consultar(cuit)
        except Exception as e:
            raise UserError(error_msg % (self.name, cuit, e))

        if not padron.denominacion or padron.denominacion == ", ":
            raise UserError(error_msg % (self.name, cuit, "La afip no devolvió nombre"))
        vals = self.parse_census_vals(padron)
        return vals

    def l10n_ar_afipws_fe_min_ammount(self):
        for record in self:
            if record.l10n_ar_vat:
                ws = self.env.user.company_id.get_connection("wsfecred").connect()
                res = ws.ConsultarMontoObligadoRecepcion(record.l10n_ar_vat)
                record.mipyme_required = True if ws.Resultado == "S" else False
                record.mipyme_from_amount = float(res)