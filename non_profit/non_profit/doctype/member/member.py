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


	def validate(self):
		if self.email_id:
			self.validate_email_type(self.email_id)
			self.generate_qr_code()
			self.send_email_to_member()

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
		if not self.qr_code:
			if self.name and self.member_name and self.email_id:
				from print_designer.print_designer.page.print_designer.print_designer import get_barcode
				arguments = {
					"barcode_format": "qrcode",
					"barcode_value": self.member_name + " - " + self.name,
					"options": {"background":"#ffffff","quiet_zone":1,"foreground":"#142b91"}
					}
				try:
					self.qr_code = get_barcode(arguments)["value"]
				except Exception as e:
					frappe.log_error(frappe.get_traceback(), _("QR Code Generation Failed"))
			else:
				frappe.throw("Please provide all the details")


	def send_email_to_member(self):
		from frappe.core.doctype.communication.email import make
		args = {
			"doctype" : "Member",
			"name" : self.name,
			"content" : f"<h3><i>Your Personal certified NHIF Notice has been generated.<br><br>Please <a href='https://rupha.ruphasoft.com/api/method/frappe.utils.print_format.download_pdf?doctype=Member&name={self.name}&key=None'>Click Here</a> to Download.</i></h3>",
			"subject" : "NHIF Notice",
			"sent_or_received" : "Sent",
			"sender" : "RUPHA",
			"recipients" : [self.email_id],
			"communication_medium" : "Email",
			"print_html" : None,
			"print_format" : "RUPHA-NOTICE"
		}
		# :param doctype: Reference DocType.
		# :param name: Reference Document name.
		# :param content: Communication body.
		# :param subject: Communication subject.
		# :param sent_or_received: Sent or Received (default **Sent**).
		# :param sender: Communcation sender (default current user).
		# :param recipients: Communication recipients as list.
		# :param communication_medium: Medium of communication (default **Email**).
		# :param send_email: Send via email (default **False**).
		# :param print_html: HTML Print format to be sent as attachment.
		# :param print_format: Print Format name of parent document to be sent as attachment.
		# :param attachments: List of File names or dicts with keys "fname" and "fcontent"
		# :param send_me_a_copy: Send a copy to the sender (default **False**).
		# :param email_template: Template which is used to compose mail .
		# :param send_after: Send after the given datetime.
		try:
			make(args)
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
