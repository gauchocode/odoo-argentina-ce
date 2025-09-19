from odoo import models
import logging

_logger = logging.getLogger(__name__)


class AccountVatLedgerXlsx(models.AbstractModel):
    _name = "report.account_vat_ledger_xlsx"
    _description = "report vat ledger in xlsx"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, vat_ledger):
        """Genera el reporte de IVA en formato XLSX, agregando la columna
        'Jurisdiccion' con la provincia del contacto."""
        if vat_ledger.invoice_ids:
            report_name = "IVA Ventas/Compras"
            sheet = workbook.add_worksheet(report_name[:31])
            money_format = workbook.add_format({"num_format": "$#,##0"})
            bold = workbook.add_format({"bold": True})
            sheet.write(1, 0, vat_ledger.display_name, bold)

            # === TITULOS ===
            titles = [None] * 25
            titles[0] = "Fecha"
            titles[1] = "Cliente/Proveedor"
            titles[2] = "CUIT"
            titles[3] = "Tipo Comprobante"
            titles[4] = "Responsabilidad AFIP"
            titles[5] = "N° Comprobante"
            titles[6] = "Jurisdiccion"  # <<--- Nueva columna
            titles[7] = "NO gravado/Exento"
            titles[8] = "Monto gravado 2,5%"
            titles[9] = "IVA 2,5%"
            titles[10] = "Monto gravado 5%"
            titles[11] = "IVA 5%"
            titles[12] = "Monto gravado 10,5%"
            titles[13] = "IVA 10.5%"
            titles[14] = "Monto gravado 21%"
            titles[15] = "IVA 21%"
            titles[16] = "Monto gravado 27%"
            titles[17] = "IVA 27%"
            titles[18] = "Percepciones"
            titles[19] = "Otros"
            titles[20] = "Total"

            for i, title in enumerate(titles):
                if title:
                    sheet.write(3, i, title, bold)

            row = 4
            index = 0
            sheet.set_column("A:G", 30)

            # === FILAS DE FACTURAS ===
            for i, obj in enumerate(vat_ledger.invoice_ids):
                sheet.write(row + index, 0, obj.invoice_date.strftime("%Y-%m-%d"))
                sheet.write(row + index, 1, obj.partner_name)
                sheet.write(row + index, 2, obj.cuit)
                sheet.write(row + index, 3, obj.document_type_id.display_name)
                sheet.write(row + index, 4, obj.afip_responsibility_type_name)
                sheet.write(row + index, 5, obj.move_name)
                # Jurisdiccion (provincia del contacto)
                jurisdiccion = obj.partner_id.state_id.name if obj.partner_id.state_id else ""
                sheet.write(row + index, 6, jurisdiccion)
                sheet.write(row + index, 7, obj.not_taxed, money_format)
                sheet.write(row + index, 8, obj.base_25, money_format)
                sheet.write(row + index, 9, obj.vat_25, money_format)
                sheet.write(row + index, 10, obj.base_5, money_format)
                sheet.write(row + index, 11, obj.vat_5, money_format)
                sheet.write(row + index, 12, obj.base_10, money_format)
                sheet.write(row + index, 13, obj.vat_10, money_format)
                sheet.write(row + index, 14, obj.base_21, money_format)
                sheet.write(row + index, 15, obj.vat_21, money_format)
                sheet.write(row + index, 16, obj.base_27, money_format)
                sheet.write(row + index, 17, obj.vat_27, money_format)
                sheet.write(row + index, 18, obj.vat_per, money_format)
                sheet.write(row + index, 19, obj.other_taxes, money_format)
                sheet.write(row + index, 20, obj.total, money_format)
                index += 1

            # === SUMATORIAS ===
            total_row = row + index
            sheet.write(total_row, 5, "Totales", bold)

            # Ajustamos acumuladores para las columnas numéricas (a partir de 7 ahora)
            totals = {col: 0 for col in range(7, 21)}

            for obj in vat_ledger.invoice_ids:
                totals[7] += obj.not_taxed or 0
                totals[8] += obj.base_25 or 0
                totals[9] += obj.vat_25 or 0
                totals[10] += obj.base_5 or 0
                totals[11] += obj.vat_5 or 0
                totals[12] += obj.base_10 or 0
                totals[13] += obj.vat_10 or 0
                totals[14] += obj.base_21 or 0
                totals[15] += obj.vat_21 or 0
                totals[16] += obj.base_27 or 0
                totals[17] += obj.vat_27 or 0
                totals[18] += obj.vat_per or 0
                totals[19] += obj.other_taxes or 0
                totals[20] += obj.total or 0

            for col, value in totals.items():
                sheet.write(total_row, col, value, money_format)
