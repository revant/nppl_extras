# License: license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	item_map = get_item_details(filters)
	iwb_map = get_item_warehouse_map(filters)
	data = []
	bal_kg, bal_packets, bal_bags = "","",""
	for (company, item, warehouse) in sorted(iwb_map):
		qty_dict = iwb_map[(company, item, warehouse)]

		# Calculate UOM Table for NPPL
		bal_kg = qty_dict.bal_qty if item_map[item]["stock_uom"] == "Kg" \
			else convert_to_uom(item, qty_dict.bal_qty, item_map[item]["stock_uom"], "Kg")

		bal_packets = qty_dict.bal_qty if item_map[item]["stock_uom"] == "Packets" \
			else convert_to_uom(item, qty_dict.bal_qty, item_map[item]["stock_uom"], "Packets")

		bal_bags = qty_dict.bal_qty if item_map[item]["stock_uom"] == "Bags" \
			else convert_to_uom(item, qty_dict.bal_qty, item_map[item]["stock_uom"], "Bags")

		data.append([item, item_map[item]["item_name"],
			item_map[item]["item_group"],
			item_map[item]["brand"],
			item_map[item]["description"], warehouse,
			item_map[item]["stock_uom"], qty_dict.opening_qty,
			qty_dict.opening_val, qty_dict.in_qty,
			qty_dict.in_val, qty_dict.out_qty,
			qty_dict.out_val, qty_dict.bal_qty,
			bal_kg, bal_packets, bal_bags,
			qty_dict.bal_val, qty_dict.val_rate,
			company
		])

	return columns, data

def get_columns(filters):
	"""return columns based on filters"""

	columns = [
		_("Item")+":Link/Item:100",
		_("Item Name")+"::150",
		_("Item Group")+"::100",
		_("Brand")+"::90",
		_("Description")+"::140",
		_("Warehouse")+":Link/Warehouse:100",
		_("Stock UOM")+":Link/UOM:90",
		_("Opening Qty")+":Float:100",
		_("Opening Value")+":Float:110",
		_("In Qty")+":Float:80",
		_("In Value")+":Float:80",
		_("Out Qty")+":Float:80",
		_("Out Value")+":Float:80",
		_("Balance Qty")+":Float:100",
		_("Kg")+"::100",
		_("Packets")+"::100",
		_("Bags")+"::100",
		_("Balance Value")+":Float:100",
		_("Valuation Rate")+":Float:90",
		_("Company")+":Link/Company:100"
	]

	return columns

def get_conditions(filters):
	conditions = ""
	if not filters.get("from_date"):
		frappe.throw(_("'From Date' is required"))

	if filters.get("to_date"):
		conditions += " and posting_date <= '%s'" % frappe.db.escape(filters["to_date"])
	else:
		frappe.throw(_("'To Date' is required"))

	if filters.get("item_code"):
		conditions += " and item_code = '%s'" % frappe.db.escape(filters.get("item_code"), percent=False)

	return conditions

#get all details
def get_stock_ledger_entries(filters):
	conditions = get_conditions(filters)
	return frappe.db.sql("""select item_code, warehouse, posting_date, actual_qty, valuation_rate,
			company, voucher_type, qty_after_transaction, stock_value_difference
		from `tabStock Ledger Entry` force index (posting_sort_index)
		where docstatus < 2 %s order by posting_date, posting_time, name""" %
		conditions, as_dict=1)

def get_item_warehouse_map(filters):
	iwb_map = {}
	from_date = getdate(filters["from_date"])
	to_date = getdate(filters["to_date"])

	sle = get_stock_ledger_entries(filters)

	for d in sle:
		key = (d.company, d.item_code, d.warehouse)
		if key not in iwb_map:
			iwb_map[key] = frappe._dict({
				"opening_qty": 0.0, "opening_val": 0.0,
				"in_qty": 0.0, "in_val": 0.0,
				"out_qty": 0.0, "out_val": 0.0,
				"bal_qty": 0.0, "bal_val": 0.0,
				"val_rate": 0.0, "uom": None
			})

		qty_dict = iwb_map[(d.company, d.item_code, d.warehouse)]

		if d.voucher_type == "Stock Reconciliation":
			qty_diff = flt(d.qty_after_transaction) - qty_dict.bal_qty
		else:
			qty_diff = flt(d.actual_qty)

		value_diff = flt(d.stock_value_difference)

		if d.posting_date < from_date:
			qty_dict.opening_qty += qty_diff
			qty_dict.opening_val += value_diff

		elif d.posting_date >= from_date and d.posting_date <= to_date:
			if qty_diff > 0:
				qty_dict.in_qty += qty_diff
				qty_dict.in_val += value_diff
			else:
				qty_dict.out_qty += abs(qty_diff)
				qty_dict.out_val += abs(value_diff)

		qty_dict.val_rate = d.valuation_rate
		qty_dict.bal_qty += qty_diff
		qty_dict.bal_val += value_diff

	return iwb_map

def get_item_details(filters):
	item_map = {}
	for d in frappe.db.sql("select name, item_name, stock_uom, item_group, brand, \
		description from tabItem", as_dict=1):
		item_map.setdefault(d.name, d)

	return item_map

def convert_to_uom(item, qty, from_uom, to_uom):
	out = " "
	con_rate = get_conversion_rate(item)
	if from_uom == "Kg":
		if to_uom == "Packets":
			out = qty * con_rate.get("to_packets")
		elif to_uom == "Bags":
			out = qty * con_rate.get("to_bags")

	if from_uom == "Packets":
		if to_uom == "Kg":
			out = qty * con_rate.get("to_kg")
		elif to_uom == "Bags":
			out = qty * con_rate.get("to_bags")

	if from_uom == "Bags":
		if to_uom == "Kg":
			out = qty * con_rate.get("to_kg")
		elif to_uom == "Packets":
			out = qty * con_rate.get("to_packets")
	return out

def get_conversion_rate(item):
	to_kg, to_packets, to_bags = 0,0,0
	bom_name = frappe.db.get_value("BOM", {"item":item, "is_default":1}, "name")
	quantity = flt(frappe.db.get_value("BOM", {"item":item, "is_default":1}, "quantity"))
	qty = flt(frappe.db.get_value("BOM Item", {"parent":bom_name,"idx":1}, "qty"))
	if frappe.get_value("Item", {"name":item}, "stock_uom") == "Kg":
		to_kg = 1
		if quantity and qty:
			to_packets = qty / quantity
			to_bags = qty * quantity # if any error use that
	elif frappe.get_value("Item", {"name":item}, "stock_uom") == "Packets":
		to_packets = 1
		if quantity and qty:
			to_kg = qty / quantity
			to_bags = flt(1 / (quantity * qty),4)
	elif frappe.get_value("Item", {"name":item}, "stock_uom") == "Bags":
		to_bags = 1
		if quantity and qty:
			to_packets = qty / quantity
			to_kg = quantity / qty # use this

	out = {
		"to_kg": to_kg,
		"to_packets": to_packets,
		"to_bags": to_bags
	}

	return out
