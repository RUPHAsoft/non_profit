# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.model.document import Document
from frappe.utils import cint, get_link_to_form

from payments.utils import get_payment_gateway_controller

from non_profit.non_profit.doctype.membership_type.membership_type import get_membership_type


class Member(Document):
	def onload(self):
		"""Load address and contacts in `__onload`"""
		load_address_and_contact(self)

	def after_insert(self):
		self.generate_qr_code()
		self.send_email_to_member()

	def validate(self):
		if self.email_id:
			self.validate_email_type(self.email_id)


	def validate_email_type(self, email):
		from frappe.utils import validate_email_address
		validate_email_address(email.strip(), True)

	def setup_subscription(self):
		non_profit_settings = frappe.get_doc('Non Profit Settings')
		if not non_profit_settings.enable_razorpay_for_memberships:
			frappe.throw(_('Please check Enable Razorpay for Memberships in {0} to setup subscription')).format(
				get_link_to_form('Non Profit Settings', 'Non Profit Settings'))

		controller = get_payment_gateway_controller("Razorpay")
		settings = controller.get_settings({})

		plan_id = frappe.get_value("Membership Type", self.membership_type, "razorpay_plan_id")

		if not plan_id:
			frappe.throw(_("Please setup Razorpay Plan ID"))

		subscription_details = {
			"plan_id": plan_id,
			"billing_frequency": cint(non_profit_settings.billing_frequency),
			"customer_notify": 1
		}

		args = {
			'subscription_details': subscription_details
		}

		subscription = controller.setup_subscription(settings, **args)

		return subscription


	def generate_qr_code(self):
		if not self.qr_code  or self.qr_code == "":
			if self.name and self.member_name and self.email_id:
				frappe.msgprint("Member Auth QR Code:")
				from print_designer.print_designer.page.print_designer.print_designer import get_barcode
				arguments = {
					"scale": 3,
					"background": "#ffffff",
					"module_color": "#142b91",
					"quiet_zone":1,
					}
				try:
					self.qr_code = get_barcode(barcode_value = self.member_name + " - " + self.name,options=arguments,barcode_format="qrcode")["value"]
					frappe.msgprint(self.qr_code)
					self.save()
				except Exception as e:
					frappe.log_error(frappe.get_traceback(), _("QR Code Generation Failed"))
			else:
				frappe.throw("Please provide all the details")


	def send_email_to_member(self):
		from frappe.core.doctype.communication.email import make
		footer = '<hr><small><i>\
			This email and any files transmitted with it are confidential and intended solely for the use of the individual or entity to \
			whom they are addressed. If you have received this email in error please notify the system manager. This message contains \
			confidential information and is intended only for the individual named. If you are not the named addressee you should not \
            disseminate, distribute or copy this e-mail. Please notify the sender immediately by e-mail if you have received this e-mail \
            by mistake and delete this e-mail from your system. If you are not the intended recipient you are notified that disclosing, \
            copying, distributing or taking any action in reliance on the contents of this information is strictly prohibited.\
			</i></small><br>\
			<strong>Rural Private Hospitals Association (RUPHA)</strong><br>\
			2nd Floor, Lungalunga Square, Off Lungalunga Street, Industrial Area Nairobi, Kenya | Email Address: info@rupha.co.ke<br>\
			http://www.rupha.co.ke/<br>\
			<h4><strong>Powered by RUPHAsoft</strong></h4>\
		'
		args = {
			"doctype" : "Member",
			"name" : self.name,
			"content" : f"Dear Member,<br><br><h3><i>Your institution's unique NHIF Notice has been auto generated.</i></h3><br><br>Please <a href='https://rupha.ruphasoft.com/api/method/frappe.utils.print_format.download_pdf?doctype=Member&name={self.name}&key=None'>Click Here</a> to Download. or see attached document<br>"+ footer,
			"subject" : "NHIF Notice",
			"sent_or_received" : "Sent",
			"sender" : "noreply@rupha.co.ke",
			"sender_full_name": "RUPHA - Powered by RUPHAsoft",
			"send_email": 1,
			"recipients" : [self.email_id],
			"communication_medium" : "Email",
			"print_html" : None,
			"print_format" : "RUPHA-NOTICE"
		}
		
		try:
			comm = make(
				doctype = args["doctype"],
				name = args["name"],
				content = args["content"],
				subject = args["subject"],
				sent_or_received = args["sent_or_received"],
				sender = args["sender"],
				sender_full_name = args["sender_full_name"],
				send_email = args["send_email"],
				recipients = args["recipients"],
				communication_medium = args["communication_medium"],
				print_html = args["print_html"],
				print_format = args["print_format"]
			)
			# comm = frappe.get_doc(
			# 	{
			# 		"doctype": "Communication",
			# 		"subject": self.subject,
			# 		"content": self.get_message(),
			# 		"sent_or_received": "Sent",
			# 		"reference_doctype": self.reference_doctype,
			# 		"reference_name": self.reference_name,
			# 	}
			# )
			# comm.insert(ignore_permissions=True)
			# comm.send_email()
			# emails_not_sent_to = comm.exclude_emails_list(include_sender=send_me_a_copy)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), _("Member Email Sending Failed"))


	@frappe.whitelist()
	def make_customer_and_link(self):
		if self.customer:
			frappe.msgprint(_("A customer is already linked to this Member"))

		customer = create_customer(frappe._dict({
			'fullname': self.member_name,
			'email': self.email_id,
			'phone': None
		}))

		self.customer = customer
		self.save()
		frappe.msgprint(_("Customer {0} has been created succesfully.").format(self.customer))


def get_or_create_member(user_details):
	member_list = frappe.get_all("Member", filters={'email': user_details.email, 'membership_type': user_details.plan_id})
	if member_list and member_list[0]:
		return member_list[0]['name']
	else:
		return create_member(user_details)

def create_member(user_details):
	user_details = frappe._dict(user_details)
	member = frappe.new_doc("Member")
	member.update({
		"member_name": user_details.fullname,
		"email_id": user_details.email,
		"pan_number": user_details.pan or None,
		"membership_type": user_details.plan_id,
		"customer_id": user_details.customer_id or None,
		"subscription_id": user_details.subscription_id or None,
		"subscription_status": user_details.subscription_status or ""
	})

	member.insert(ignore_permissions=True)
	member.customer = create_customer(user_details, member.name)
	member.save(ignore_permissions=True)

	return member

def create_customer(user_details, member=None):
	customer = frappe.new_doc("Customer")
	customer.customer_name = user_details.fullname
	customer.customer_type = "Individual"
	customer.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group")
	customer.territory = frappe.db.get_single_value("Selling Settings", "territory")
	customer.flags.ignore_mandatory = True
	customer.insert(ignore_permissions=True)

	try:
		frappe.db.savepoint("contact_creation")
		contact = frappe.new_doc("Contact")
		contact.first_name = user_details.fullname
		if user_details.mobile:
			contact.add_phone(user_details.mobile, is_primary_phone=1, is_primary_mobile_no=1)
		if user_details.email:
			contact.add_email(user_details.email, is_primary=1)
		contact.insert(ignore_permissions=True)

		contact.append("links", {
			"link_doctype": "Customer",
			"link_name": customer.name
		})

		if member:
			contact.append("links", {
				"link_doctype": "Member",
				"link_name": member
			})

		contact.save(ignore_permissions=True)

	except frappe.DuplicateEntryError:
		return customer.name

	except Exception as e:
		frappe.db.rollback(save_point="contact_creation")
		frappe.log_error(frappe.get_traceback(), _("Contact Creation Failed"))
		pass

	return customer.name

@frappe.whitelist(allow_guest=True)
def create_member_subscription_order(user_details):
	"""Create Member subscription and order for payment

	Args:
		user_details (TYPE): Description

	Returns:
		Dictionary: Dictionary with subscription details
		{
			'subscription_details': {
										'plan_id': 'plan_EXwyxDYDCj3X4v',
										'billing_frequency': 24,
										'customer_notify': 1
									},
			'subscription_id': 'sub_EZycCvXFvqnC6p'
		}
	"""

	user_details = frappe._dict(user_details)
	member = get_or_create_member(user_details)

	subscription = member.setup_subscription()

	member.subscription_id = subscription.get('subscription_id')
	member.save(ignore_permissions=True)

	return subscription

@frappe.whitelist()
def register_member(fullname, email, rzpay_plan_id, subscription_id, pan=None, mobile=None):
	plan = get_membership_type(rzpay_plan_id)
	if not plan:
		raise frappe.DoesNotExistError

	member = frappe.db.exists("Member", {'email': email, 'subscription_id': subscription_id })
	if member:
		return member
	else:
		member = create_member(dict(
			fullname=fullname,
			email=email,
			plan_id=plan,
			subscription_id=subscription_id,
			pan=pan,
			mobile=mobile
		))

		return member.name
