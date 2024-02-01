# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class EventParticipant(Document):
	def onload(self):
		pass
	
	def after_insert(self):
		self.send_email_to_member()

	def validate(self):
		pass 	

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

		payment_instructions = '<br><h3><strong>Payment Options:</strong></h3><br>\
			<strong><u>BANK DETAILS</u></strong>\
			<strong>BANK DETAILS</strong> : EQUITY BANK (KENYA) LIMITED<br>\
			<strong>ACCOUNT NAME RURAL PRIVATE HOSPITALS ASSOCIATION OF KENYA</strong><br>\
			<strong>BANK ACCOUNT NO :</strong> 17602-8136-2990 -KES<br>\
			<strong>1760284516849 -USD</strong><br>\
			<strong>BANK SWIFT CODE :</strong> EQBLKENAXXX<br>\
			<strong>BANK CODE:</strong> 068<br>\
			<strong>BRANCH CODE:</strong> 176<br>\
			<strong>BRANCH NAME SYOKIMAU GATEWAY MALL BRANCH</strong><br>\
			<strong><u>MPESA</u></strong><br>\
			<strong>PAYBILL:</strong> 247247<br>\
			<strong>ACCOUNT NO:</strong> 176 028 136 2990<br>\
			<strong>ACCOUNT NAME :</strong> RURAL PRIVATE HOSPITALS ASSOCIATION OF KENYA<br><br>'

		# <a href='https://rupha.ruphasoft.com/api/method/frappe.utils.print_format.download_pdf?doctype=Member&name={self.name}&key=None'>Click Here</a> to Download. or see attached document<br>
		args = {
			"doctype" : "Event Participant",
			"name" : self.name,
			"content" : f"Dear {self.participant_name},<br><br><h3><i>Your participation request has been received.</i></h3><br><br> "+payment_instructions+ footer,
			"subject" : "RUPHA's 5th Annual Convention",
			"sent_or_received" : "Sent",
			"sender" : "noreply@rupha.co.ke",
			"sender_full_name": "RUPHA - Powered by RUPHAsoft",
			"send_email": 1,
			"recipients" : [self.email],
			"cc" : ["info@rupha.co.ke","cmunene@rupha.co.ke"],
			"bcc" : ["mohamud@rupha.co.ke"],
			"communication_medium" : "Email",
			"print_html" : None,
			"has_attachment": 1,
			"print_format" : "Event Participant"
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
				print_format = args["print_format"],
				cc = args["cc"],
				bcc = args["bcc"],
				has_attachment = args["has_attachment"]
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
			frappe.log_error(frappe.get_traceback(), _("participant Email Sending Failed"))
