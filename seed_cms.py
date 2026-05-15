#!/usr/bin/env python3
"""
Seed script to populate CMS with existing page content in Czech and English.
Usage: python seed_cms.py
"""

import os
import html as html_module
import re
import sys
from uuid import uuid4
from sqlalchemy.orm import Session

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db.session import get_db, SessionLocal
from app.models.cms import Page, PageSection
from app.core.config import get_settings


SCRIPT_DIR = os.path.dirname(__file__)
LEGAL_DOCS_DIR = os.path.join(SCRIPT_DIR, "legal_docs")
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))


def _extract_html_fragment(raw_html: str) -> str:
    """Keep the meaningful HTML fragment from Word-exported documents."""
    fragment_match = re.search(r"<!--StartFragment-->(.*?)<!--EndFragment-->", raw_html, flags=re.IGNORECASE | re.DOTALL)
    if fragment_match:
        return html_module.unescape(fragment_match.group(1).strip())

    body_match = re.search(r"<body[^>]*>(.*?)</body>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    if body_match:
        return html_module.unescape(body_match.group(1).strip())

    return html_module.unescape(raw_html.strip())


def _has_visible_text(raw_html: str) -> bool:
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html_module.unescape(text)
    return bool(re.search(r"\w", text))


def _format_fallback_html(title: str, description: str) -> str:
    return (
        f"<h1>{html_module.escape(title)}</h1>"
        f"<p>{html_module.escape(description)}</p>"
    )


def _load_legal_html(filename: str, fallback: str) -> str:
    """Load legal page HTML from project root; use fallback when unavailable."""
    candidate_paths = [
        os.path.join(LEGAL_DOCS_DIR, filename),
        os.path.join(SCRIPT_DIR, filename),
        os.path.join(PROJECT_ROOT, filename),
    ]
    for file_path in candidate_paths:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                fragment = _extract_html_fragment(f.read())
                if _has_visible_text(fragment):
                    return fragment
        except OSError:
            continue
    return fallback


PRIVACY_POLICY_HTML_CS = _load_legal_html(
    "AuditReady_Privacy_Policy.html",
    _format_fallback_html(
        "Zásady ochrany osobních údajů",
        "Vaše soukromí je pro nás důležité. Tyto zásady ochrany osobních údajů vysvětlují, jak shromažďujeme a používáme vaše informace.",
    ),
)

COOKIE_POLICY_HTML_CS = _load_legal_html(
    "AuditReady_Cookie_Policy.html",
    _format_fallback_html(
        "Zásady cookies",
        "Používáme cookies ke zlepšení vaší zkušenosti. Zjistěte více o tom, jak je používáme.",
    ),
)

# Optional English legal documents (if provided by client as translated HTML files)
PRIVACY_POLICY_HTML_EN = _load_legal_html(
    "AuditReady_Privacy_Policy_en.html",
    """
<h1>Privacy Policy / Personal Data Processing Policy</h1>
<h2>1. Identification of the data controller</h2>
<p>The controller of personal data is:</p>
<p>AuditReady s.r.o., with its registered office at Francouzská 312/100, Vršovice, 101 00 Prague 10, Company ID (IČO) 06584128, registered in the Commercial Register kept by the Municipal Court in Prague, section C, file 284828, and as the controller we process your personal data.</p>
<h2>2. Scope of this policy</h2>
<p>This policy applies to the processing of personal data that occurs in connection with the operation of the Auditready website, the use of the Auditready web application and the provision of related services.</p>
<p>This policy applies in particular to the following persons:</p>
<ul>
<li>visitors of the Auditready website,</li>
<li>persons who contact us through the contact form, e-mail or another communication channel,</li>
<li>prospects interested in our services,</li>
<li>customers and their contact persons,</li>
<li>users of the Auditready web application,</li>
<li>persons whose data may be contained in materials, notes, answers or documents uploaded or entered by the customer.</li>
</ul>
<p>This policy applies both to the processing of data during ordinary use of the website and to the processing of data within the user account, the online checklist, the evaluation of answers, the creation of the output report, billing, technical support and ensuring the security of the service.</p>
<p>If a customer uploads documents, notes or other materials containing personal data of third parties into the Auditready web application, the customer is responsible for ensuring that they are entitled to upload such data and that doing so does not violate the rights of the persons concerned or any other legal obligations.</p>
<h2>3. What personal data we process</h2>
<p>In connection with the operation of the website, the web application and the provision of Auditready services, we may process various categories of personal data. The scope of the data processed depends on whether you are only a visitor of the website, contact us, create a user account, use our service or act as a customer contact person.</p>
<section>
<h3>3.1 Website visitor data</h3>
<p>When you visit the Auditready website, we may process in particular technical data related to the use of the site, such as:</p>
<ul>
<li>IP address,</li>
<li>type of device, browser and operating system,</li>
<li>date and time of the visit,</li>
<li>pages visited,</li>
<li>information about your behaviour on the website, if you give consent through the cookie banner,</li>
<li>cookie settings and information about consent granted or refused.</li>
</ul>
<p>This data is processed in particular to ensure the proper functioning of the website, its security, basic technical administration and, where applicable, traffic measurement, if the user consents to it.</p>
</section>
<section>
<h3>3.2 Data of persons who contact us</h3>
<p>If you contact us through the contact form, e-mail, telephone or any other communication channel, we may process in particular:</p>
<ul>
<li>first name and last name,</li>
<li>e-mail address,</li>
<li>telephone number, if you provide it,</li>
<li>organisation name,</li>
<li>job position or role in the organisation, if you provide it,</li>
<li>content of the message,</li>
<li>other information that you communicate to us in the course of the communication.</li>
</ul>
<p>We process this data in order to handle your enquiry, prepare an offer, communicate with the prospect or customer and conduct related business communication.</p>
</section>
<section>
<h3>3.3 Data of customers and users of the web application</h3>
<p>If you use the Auditready web application or related online services, we may process in particular:</p>
<ul>
<li>first name and last name of the user,</li>
<li>e-mail address,</li>
<li>organisation name,</li>
<li>company ID (IČO) and billing data of the organisation,</li>
<li>role or permissions of the user within the application,</li>
<li>login and identification data of the user account,</li>
<li>data about the use of the service,</li>
<li>history of orders, payments and generated outputs,</li>
<li>communication with technical or customer support.</li>
</ul>
<p>This data is necessary in particular for the creation and management of the user account, providing access to the purchased service, managing the customer relationship, billing and user support.</p>
</section>
<section>
<h3>3.4 Data entered into the online checklist and related materials</h3>
<p>When using the Auditready web application, the customer or user may enter answers, notes, documents or other materials related to the assessment of the organisation’s readiness.</p>
<p>This data may include in particular:</p>
<ul>
<li>answers to questions in the online checklist,</li>
<li>notes and comments by the user,</li>
<li>information about the organisation, its processes, technical and organisational measures,</li>
<li>information about security documentation,</li>
<li>uploaded files and supporting evidence,</li>
<li>information contained in the generated output report.</li>
</ul>
<p>In some cases, these materials may also contain personal data of third parties, such as names of employees, contact details, work roles or information contained in the customer’s internal documents. The customer is responsible for ensuring that only such data is entered into the application as the customer is entitled to process and transfer to AuditReady s.r.o. for the purpose of providing the service.</p>
</section>
<section>
<h3>3.5 Payment and billing data</h3>
<p>In connection with ordering and paying for the service, we may process in particular:</p>
<ul>
<li>identification and billing data of the customer,</li>
<li>organisation name,</li>
<li>company ID (IČO) and VAT ID (DIČ), where relevant,</li>
<li>billing address,</li>
<li>contact e-mail for sending invoices,</li>
<li>data about the ordered service,</li>
<li>payment status,</li>
<li>payment or transaction identifier,</li>
<li>data necessary for issuing and keeping accounting and tax documents.</li>
</ul>
<p>We do not process payment card data directly if the payment is made through an external payment service provider. In such a case, the payment data is processed directly by that provider in accordance with its own rules and terms.</p>
</section>
<section>
<h3>3.6 Technical, operational and security data</h3>
<p>In order to ensure the security, availability and proper operation of the website and the web application, we may also process technical, operational and security data, such as:</p>
<ul>
<li>IP address,</li>
<li>time of login and logout,</li>
<li>records of access to the user account,</li>
<li>information about actions performed within the application,</li>
<li>technical logs,</li>
<li>information about application errors,</li>
<li>data necessary to prevent misuse of the service, unauthorised access or security incidents.</li>
</ul>
<p>We process this data in particular to protect user accounts, protect customer data, detect technical problems, ensure operation of the service and protect the rights and legitimate interests of AuditReady s.r.o.</p>
</section>
<h2>4. Purposes and legal bases of processing</h2>
<p>We process personal data only to the extent necessary for the specific purposes set out below. For each purpose of processing, we assign a corresponding legal basis under the General Data Protection Regulation (GDPR).</p>
<section>
<h3>4.1 Operation of the website and ensuring its functionality</h3>
<p>We process personal and technical data of website visitors in order to ensure the proper functioning of the website, its security, availability, basic technical administration and display of content.</p>
<p>The legal basis for this processing is the controller’s legitimate interest in operating, administering and securing the website. For strictly necessary cookies, the processing is necessary to ensure the functionality of the website.</p>
</section>
<section>
<h3>4.2 Communication with prospects, customers and other persons</h3>
<p>If you contact us through e-mail, the contact form, telephone or another communication channel, we process the data provided in order to handle your enquiry, reply to your message, prepare an offer, negotiate the terms of cooperation or conduct follow-up business communication.</p>
<p>Depending on the nature of the communication, the legal basis is the implementation of pre-contractual measures, the performance of a contract or the controller’s legitimate interest in conducting business communication and handling enquiries.</p>
</section>
<section>
<h3>4.3 Creation and management of the user account</h3>
<p>We process personal data of web application users in order to create, manage and secure the user account, verify the user’s identity, set permissions, manage access and enable the use of the purchased service.</p>
<p>The legal basis is the performance of a contract or, where applicable, the implementation of pre-contractual measures. For security measures, the legal basis may also be the controller’s legitimate interest in protecting the service, user accounts and customer data.</p>
</section>
<section>
<h3>4.4 Provision of the Auditready service and creation of the output report</h3>
<p>We process data entered into the web application, in particular checklist answers, notes, comments, information about the organisation and, where applicable, uploaded materials, in order to provide the Auditready service, evaluate the answers entered and generate the output report.</p>
<p>The legal basis is the performance of the contract between the customer and AuditReady s.r.o. If the customer enters personal data of third parties into the application, the customer is responsible for having an appropriate legal basis for such processing.</p>
</section>
<section>
<h3>4.5 Billing, accounting and compliance with legal obligations</h3>
<p>We process identification, billing and payment data in order to process the order, receive payment for the service, issue tax and accounting documents, maintain accounting records and comply with other legal obligations.</p>
<p>The legal basis is the performance of the contract and compliance with legal obligations applicable to the controller, in particular in the area of accounting and taxes.</p>
</section>
<section>
<h3>4.6 Technical support and handling of user requests</h3>
<p>We process data provided through communication with technical or customer support in order to handle user requests, technical issues, complaints, enquiries and to ensure the proper operation of the service.</p>
<p>The legal basis is the performance of a contract or, where applicable, the controller’s legitimate interest in providing support, resolving issues and improving the service.</p>
</section>
<section>
<h3>4.7 Service security, account protection and prevention of misuse</h3>
<p>We process technical, operational and security data in order to protect the website, web application, user accounts, customer data and infrastructure. This data may be used in particular to detect errors, unauthorised access, suspicious activity, security incidents or other misuse of the service.</p>
<p>The legal basis is the controller’s legitimate interest in protecting the service, customers, data, infrastructure and legal claims.</p>
</section>
<section>
<h3>4.8 Web analytics and service improvement</h3>
<p>If you give consent through the cookie banner or another similar tool, we may process data about the use of the website in order to measure traffic, evaluate the effectiveness of content, improve the website and optimise our services.</p>
<p>The legal basis is your consent. You can withdraw or change your consent at any time through the cookie settings.</p>
</section>
<section>
<h3>4.9 Direct marketing and commercial communications</h3>
<p>To a reasonable extent, we may process contact data of customers in order to send commercial communications relating to our own similar services. In other cases, we send commercial communications only on the basis of consent.</p>
<p>The legal basis may be the controller’s legitimate interest in communicating with existing customers or the consent of the recipient, where required by law.</p>
<p>The recipient always has the right to refuse or unsubscribe from commercial communications.</p>
</section>
<section>
<h3>4.10 Protection of legal claims</h3>
<p>We may also process personal data, to the extent necessary, in order to protect our rights, resolve disputes, assert or defend legal claims, monitor compliance with contractual terms and demonstrate fulfilment of statutory or contractual obligations.</p>
<p>The legal basis is the controller’s legitimate interest in protecting its rights and legal claims.</p>
</section>
<h2>5. Data processing within the Auditready web application</h2>
<p>The Auditready web application is used for guided completion of an online checklist, addition of notes and supporting materials by the customer and creation of an output report. During the use of the application, data entered, uploaded or generated by the user during the use of the service is processed.</p>
<section>
<h3>5.1 User account and access to the application</h3>
<p>Use of the web application may require the creation of a user account. Within the account, we process in particular the user’s identification and contact data, login credentials, information about the organisation to which the user is assigned and data on the user’s permissions within the application.</p>
<p>This data is used to authenticate the user, manage access permissions, secure the account and enable the use of the purchased service. Access to the application may be protected by additional security mechanisms, for example multi-factor authentication.</p>
</section>
<section>
<h3>5.2 Completing the online checklist</h3>
<p>Within the online checklist, the user provides answers to questions concerning the readiness of the organisation in the area of cyber security, compliance with selected requirements or internal security measures.</p>
<p>The answers provided may contain information about the organisation, its processes, security measures, technical infrastructure, responsibilities and other matters relevant to the creation of the output report.</p>
</section>
<section>
<h3>5.3 Notes, comments and additional information</h3>
<p>The user may add their own notes, comments or explanations to individual questions in the application. This information serves to enable a more accurate assessment of the answers and the creation of a more relevant output report.</p>
<p>The user should include in the notes only information that is necessary for the purpose of using the service and should not enter excessive personal data, sensitive information, passwords, access tokens, private keys or other data that is not necessary for the provision of the service.</p>
</section>
<section>
<h3>5.4 Uploading materials and supporting files</h3>
<p>The application may allow the upload of documents, screenshots, exports, internal materials or other files that serve as supporting information for the completed checklist.</p>
<p>The customer is responsible for the content of uploaded files and for being entitled to upload them to the application. Before uploading files, the customer should consider whether the documents contain excessive personal data, confidential information, trade secrets or security-sensitive data that is not necessary for the purpose of the service.</p>
<p>In particular, passwords, authentication data, private cryptographic keys, access tokens, complete security configurations that are not necessary for the assessment, or other data whose upload could increase security risk for the customer or third parties should not be uploaded to the application.</p>
</section>
<section>
<h3>5.5 Creation of the output report</h3>
<p>Based on the data entered by the user, the application may generate an output report. The report may contain a summary of answers, identified gaps, recommendations, additional comments and other information derived from the data entered.</p>
<p>The output report is generated on the basis of data provided by the user. AuditReady s.r.o. is not responsible for the correctness or completeness of the data entered into the application by the customer or user.</p>
</section>
<section>
<h3>5.6 Automatic deletion of data from the application</h3>
<p>Data entered into the web application, in particular checklist answers, notes, uploaded materials and generated reports, may be retained only for a limited time necessary for the provision of the service.</p>
<p>If automatic data deletion is configured within the service, the relevant data will be deleted within the period stated in this policy or in the terms of service. After the data has been deleted, it may no longer be possible to retrieve the uploaded materials or the generated report.</p>
<p>The specific retention period is set out in the section dedicated to retention of personal data.</p>
</section>
<section>
<h3>5.7 Customer’s responsibility for the data uploaded</h3>
<p>The customer is responsible for ensuring that the data, documents and materials uploaded to the application are accurate, up to date, appropriate and that their upload to the application does not infringe the rights of third parties or any of the customer’s legal or contractual obligations.</p>
<p>If the customer uploads personal data of third parties into the application, the customer is responsible for having an appropriate legal basis for such processing and for ensuring that those persons have been informed to the necessary extent about the processing of their personal data.</p>
</section>
<h2>6. Payment and billing data</h2>
<p>In connection with ordering, paying for and billing Auditready services, we process personal and identification data necessary for the conclusion and performance of the contract, processing of the payment, issuance of the tax document and compliance with accounting and tax obligations.</p>
<p>The data processed may include in particular the customer’s name, the first name and last name of the contact person, e-mail address, billing address, company ID (IČO), VAT ID (DIČ), information about the ordered service, price, payment status, payment date, order identifier, payment or transaction identifier and other data necessary for the registration of the order and the issuance of the accounting or tax document.</p>
<p>Payments for services may be processed through an external payment service provider, in particular through Stripe Payments Europe, Ltd. If a payment is made by payment card or any other online payment method, payment card data is not processed directly by AuditReady s.r.o. but by the relevant payment service provider in accordance with its own terms and privacy policy.</p>
<p>AuditReady s.r.o. may receive from the payment service provider information necessary to confirm the payment and manage the order, such as payment status, transaction identifier, amount, currency, payment date and information about the success or failure of the payment.</p>
<p>Billing and accounting data may also be processed by an accounting or tax advisor or within an accounting or invoicing system, to the extent necessary for compliance with the legal obligations of AuditReady s.r.o.</p>
<p>The legal basis for the processing of payment and billing data is the performance of the contract, compliance with legal obligations and, to the extent necessary, also the controller’s legitimate interest in keeping records of payments, managing orders and protecting legal claims.</p>
</section>
<h2>7. Cookies and similar technologies</h2>
<p>The Auditready website and web application may use cookies and similar technologies, such as local storage or session storage, to ensure the functionality of the website, secure the service, store user preferences, measure traffic and, where applicable, improve content and services.</p>
<p>Cookies are small text files stored on the user’s device. Some cookies are necessary for the proper functioning of the website or application; others may be used only with the user’s consent.</p>
<section>
<h3>7.1 Necessary cookies</h3>
<p>We use necessary cookies and similar technologies in particular to ensure the basic functioning of the website and application, secure the service, manage logins, protect against abuse, store cookie settings and ensure the proper display of content.</p>
<p>These cookies are necessary for the provision of the service and cannot be disabled through the cookie banner. No user consent is required for their use.</p>
</section>
<section>
<h3>7.2 Analytics cookies</h3>
<p>Analytics cookies may be used to measure website traffic, understand how users interact with the website, evaluate the effectiveness of content and improve the website and services.</p>
<p>We use analytics cookies only if the user grants consent through the cookie banner or another consent management tool. The user can change or withdraw their consent at any time.</p>
</section>
<section>
<h3>7.3 Marketing cookies</h3>
<p>Marketing cookies may be used in the future to measure the effectiveness of marketing campaigns, display relevant content or evaluate conversions.</p>
<p>We use marketing cookies only on the basis of the user’s consent. If marketing cookies are not in use, this category will not be active or will be marked as unused in the cookie banner.</p>
</section>
<section>
<h3>7.4 Cookie consent management</h3>
<p>On the first visit to the website, the user may be shown a cookie banner that allows them to decide about the use of optional cookies.</p>
<p>The cookie banner should in particular allow the user to:</p>
<ul>
<li>accept all optional cookies,</li>
<li>reject all optional cookies,</li>
<li>configure individual categories of cookies as the user prefers.</li>
</ul>
<p>Necessary cookies cannot be disabled through the cookie banner because they are required for the functioning of the website or the web application. Analytics and marketing cookies are used only if the user grants consent for them.</p>
<p>The user can change or withdraw their consent at any time through the "Cookie settings" link, which should be available on the website, for example in the website footer.</p>
<p>Rejecting optional cookies does not affect the ability to use the AuditReady website or service, but it may affect some additional features, traffic measurement, content optimisation or campaign evaluation.</p>
</section>
<h2>8. Recipients and processors of personal data</h2>
<p>Personal data may only be made available to persons and entities involved in the operation of the website, the web application, the provision of Auditready services, payment processing, billing, technical support, security, accounting or compliance with legal obligations.</p>
<p>Personal data may be processed in particular by the following categories of recipients and processors:</p>
<ul>
<li>providers of hosting, cloud and infrastructure services,</li>
<li>providers of database and storage services,</li>
<li>providers of e-mail, communication and office services,</li>
<li>payment service providers, in particular Stripe Payments Europe, Ltd.,</li>
<li>providers of billing, accounting or tax services,</li>
<li>external accounting or tax advisors,</li>
<li>suppliers of development, technical administration, maintenance and support of the application,</li>
<li>providers of security, monitoring and logging services, where used and where the user has given consent,</li>
<li>public authorities, where such obligation is imposed on us by law or a legitimate request.</li>
</ul>
<p>Personal data is only handled by persons who need it for the performance of their tasks or contractual obligations. If personal data is processed by an external supplier acting as a processor, the processing is governed by a data processing agreement or another equivalent contractual arrangement.</p>
<p>AuditReady s.r.o. does not sell personal data to third parties.</p>
</section>
<h2>9. Transfers of personal data outside the EU/EEA</h2>
<p>We process personal data primarily within the European Union or the European Economic Area. However, some of our suppliers or their sub-suppliers may have their registered offices, infrastructure or support teams also outside the EU/EEA.</p>
<p>If, in connection with the provision of Auditready services, personal data were to be transferred to countries outside the EU/EEA, such transfer would take place only under the conditions laid down by data protection legislation. In particular, this may concern transfers to a country for which the European Commission has issued an adequacy decision, or transfers on the basis of appropriate safeguards, such as standard contractual clauses.</p>
<p>When selecting suppliers, we take into account whether they provide adequate legal, organisational and technical measures for the protection of personal data. Where possible and appropriate, we prefer to process and store data within the EU/EEA.</p>
<p>More detailed information about specific suppliers and any transfers of data outside the EU/EEA may be set out in this policy, in the service settings or in the documentation of the relevant provider.</p>
<h2>10. Retention period of personal data</h2>
<p>We retain personal data only for the time necessary to fulfil the purposes for which it was collected, and further for the period required by law or necessary for the protection of our rights and legal claims.</p>
<p>The specific retention period varies depending on the type of data and the purpose of its processing.</p>
<section>
<h3>10.1 Data from contact communication</h3>
<p>Data provided through the contact form, e-mail, telephone or other communication is retained for the time necessary to handle the enquiry, conduct follow-up communication and, where appropriate, to document the course of the communication.</p>
<p>If no contract is concluded, such data may be retained for up to 12 months from the last communication, unless a longer retention period is necessary in a specific case for the protection of legal claims.</p>
</section>
<section>
<h3>10.2 Customer and user account data</h3>
<p>We retain data of customers and users of the web application for the duration of the user account or the contractual relationship. After termination of the contractual relationship or deletion of the account, some data may be retained to a limited extent if necessary for compliance with legal obligations, handling of complaints, protection of legal claims or evidence of provision of the service.</p>
</section>
<section>
<h3>10.3 Data entered into the web application</h3>
<p>Data entered by the customer or user into the web application, in particular checklist answers, notes, comments, uploaded materials and generated reports, is retained only for the time necessary for the provision of the service.</p>
<p>If automatic data deletion is configured for the service, such data will be deleted no later than 48 hours after the output report has been generated, or within another period specified for the specific service or in the terms of service.</p>
<p>After the data has been deleted, it may no longer be possible to restore the uploaded materials, answers or generated report. The user is therefore responsible for downloading and saving the output report in time if they wish to use it further.</p>
</section>
<section>
<h3>10.4 Payment, billing and accounting data</h3>
<p>We retain payment, billing and accounting data for the period required by accounting, tax and related legislation. This data may be retained even after the end of the contractual relationship if necessary to fulfil the legal obligations of AuditReady s.r.o.</p>
</section>
<section>
<h3>10.5 Technical, operational and security data</h3>
<p>We retain technical, operational and security logs for the time necessary to ensure the security of the service, resolve technical issues, detect misuse, protect legal claims and ensure the operation of the website and application.</p>
<p>The standard retention period for such data is typically 6 months, unless a longer retention period is necessary in justified cases, for example when handling a security incident, suspected misuse of the service or a legal dispute.</p>
</section>
<section>
<h3>10.6 Data processed on the basis of consent</h3>
<p>Data processed on the basis of consent, such as data from analytics or marketing cookies, is processed for the duration of the consent or until it is withdrawn.</p>
<p>Specific retention periods of individual cookies may be set out in a separate Cookie Policy or in the cookie banner settings.</p>
</section>
<section>
<h3>10.7 Longer retention in justified cases</h3>
<p>In certain cases, personal data may be retained for a longer period if necessary for compliance with legal obligations, protection of legal claims, resolution of a dispute, monitoring of compliance with contractual terms or investigation of a security incident.</p>
<p>In such a case, we retain the data only to the extent necessary for the given purpose.</p>
</section>
<h2>11. Security of personal data</h2>
<p>We consider the protection of personal data and other information processed within Auditready services to be an important part of the service provided. We take appropriate technical and organisational measures to protect personal data against unauthorised access, loss, misuse, unauthorised alteration, disclosure or destruction.</p>
<p>Security measures may include in particular access control, the use of strong authentication, encryption of data transmission, role-based separation of access, securing of cloud infrastructure, back-up of selected operational components, technical logging, monitoring of operations, regular updates of systems and restricting access to personal data only to persons who need it for the performance of their tasks.</p>
<p>Access to the web application may be protected by multi-factor authentication or other security mechanisms. Users are obliged to protect their login credentials, not to share them with others and to inform us without undue delay if they suspect misuse of their credentials or unauthorised access to their account.</p>
<p>When selecting suppliers and processors, we take into account their ability to ensure an adequate level of protection of personal data. We enter into appropriate contractual arrangements with external processors who process personal data on our behalf.</p>
<p>Although we take reasonable security measures, no method of transmitting data over the internet nor any method of electronic storage can be considered entirely risk-free. If a security incident occurs that could affect the protection of personal data, we will act in accordance with applicable law and take appropriate measures to mitigate possible consequences.</p>
<h2>12. Rights of data subjects</h2>
<p>In connection with the processing of personal data, you have the rights set out by data protection legislation. You can exercise these rights against AuditReady s.r.o. using the contact details set out in this policy.</p>
<section>
<h3>12.1 Right of access to personal data</h3>
<p>You have the right to obtain confirmation as to whether we are processing your personal data. If we are processing it, you have the right to obtain access to such data and information on how it is being processed.</p>
</section>
<section>
<h3>12.2 Right to rectification</h3>
<p>You have the right to request the rectification of inaccurate personal data concerning you. If your data is incomplete, you may request its completion.</p>
</section>
<section>
<h3>12.3 Right to erasure</h3>
<p>You have the right to request the erasure of personal data if it is no longer necessary for the purposes for which it was processed, if you withdraw your consent and there is no other legal basis for the processing, if you object to the processing or if the data is being processed unlawfully.</p>
<p>The right to erasure does not apply where further retention of the data is necessary for compliance with a legal obligation, for the protection of legal claims or for another statutory reason.</p>
</section>
<section>
<h3>12.4 Right to restriction of processing</h3>
<p>You have the right to request the restriction of the processing of personal data, for example if you contest the accuracy of the data, if the processing is unlawful but you do not wish the data to be erased, or if you need the data for the establishment, exercise or defence of legal claims.</p>
</section>
<section>
<h3>12.5 Right to data portability</h3>
<p>If the processing is based on consent or on the performance of a contract and is carried out by automated means, you have the right to receive the personal data you have provided to us in a structured, commonly used and machine-readable format, and to request its transmission to another controller, where technically feasible.</p>
</section>
<section>
<h3>12.6 Right to object</h3>
<p>You have the right to object to the processing of personal data based on the controller’s legitimate interest. In such a case, we will no longer process the data unless we demonstrate compelling legitimate grounds for the processing that override your rights and interests, or unless the data is necessary for the establishment, exercise or defence of legal claims.</p>
<p>If we process personal data for direct marketing purposes, you have the right to object at any time. In such a case, your data will no longer be processed for direct marketing.</p>
</section>
<section>
<h3>12.7 Right to withdraw consent</h3>
<p>If the processing is based on your consent, you have the right to withdraw such consent at any time. The withdrawal of consent does not affect the lawfulness of processing carried out before its withdrawal.</p>
<p>You can withdraw or change consent to the use of optional cookies through the cookie settings on the website.</p>
</section>
<section>
<h3>12.8 Handling of requests</h3>
<p>We will handle your request without undue delay and at the latest within the period stipulated by law. Where necessary, we may ask you to verify your identity in order to prevent unauthorised disclosure of personal data to another person.</p>
</section>
<h2>13. Right to lodge a complaint with the supervisory authority</h2>
<p>If you believe that the processing of your personal data infringes data protection legislation, you have the right to lodge a complaint with the supervisory authority.</p>
<p>The supervisory authority in the Czech Republic is:</p>
<p>Office for Personal Data Protection (Úřad pro ochranu osobních údajů), Pplk. Sochora 27, 170 00 Prague 7, Web: www.uoou.gov.cz</p>
<p>This does not affect your right to contact AuditReady s.r.o. directly using the contact details set out in this policy. We will endeavour to resolve any questions or objections with you directly first.</p>
<h2>14. Changes to this policy</h2>
<p>We may update this policy from time to time, in particular in the event of changes to our services, the technologies used, legal requirements, processing practices or suppliers.</p>
<p>The current version of the policy will always be available on the Auditready website. If a significant change is made to the way personal data is processed, we may also inform you of such a change in another appropriate manner, for example by e-mail or a notice in the web application.</p>
<p>Changes to this policy take effect on the date of their publication, unless stated otherwise.</p>
<h2>15. Contact details for personal data protection</h2>
<p>If you have any questions regarding the processing of personal data, the exercise of your rights or other matters related to the protection of personal data, you can contact us at the address below:</p>
<p>AuditReady s.r.o. has not appointed a Data Protection Officer, as this obligation does not apply to it under the applicable legislation.</p>
<aside>
<h2>AuditReady s.r.o.</h2>
<p>Francouzská 312/100</p>
<p>Vršovice, 101 00 Prague 10</p>
<p>E-mail: info@auditready.cz</p>
</aside>
"""
)

COOKIE_POLICY_HTML_EN = _load_legal_html(
    "AuditReady_Cookie_Policy_en.html",
    """
<h1>AuditReady Cookie Policy</h1>
<p>This document describes how AuditReady s.r.o. uses cookies and similar technologies on the AuditReady website and web application.</p>
<h2>1. General information</h2>
<p>This cookie policy explains how we use cookies and similar technologies in connection with the operation of the website, the web application and the online services provided under the AuditReady brand.</p>
<p>The operator of the AuditReady website and service is:</p>
<p>AuditReady s.r.o., with its registered office at Francouzská 312/100, Vršovice, 101 00 Prague 10, Company ID (IČO): 06584128, registered in the Commercial Register kept by the Municipal Court in Prague, section C, file 284828, e-mail: info@auditready.cz.</p>
<p>This policy applies to the use of cookies and similar technologies when visiting the AuditReady website, using the web application, managing a user account and using AuditReady online services.</p>
<p>More detailed information about the processing of personal data is set out in the separate Privacy Policy available on the AuditReady website.</p>
<h2>2. What cookies and similar technologies are</h2>
<p>Cookies are small text files that may be stored on the user’s device, such as a computer, phone or tablet, when visiting a website. Cookies allow the website or application to recognise the user’s device, remember certain preferences, ensure the proper functioning of the service or obtain information about how the website is being used.</p>
<p>In addition to cookies, similar technologies may also be used, such as local storage, session storage or other technical mechanisms for storing information in the browser. For simplicity, all of these technologies are jointly referred to as "cookies" in this policy, unless expressly stated otherwise.</p>
<p>Cookies may be temporary, i.e. stored only for the duration of a website visit or browser session, or persistent, remaining on the user’s device for a certain period or until they are removed by the user.</p>
<p>Some cookies are necessary for the proper functioning of the website or application. Other cookies, such as analytics or marketing cookies, are used only if the user grants consent through the cookie banner or another consent management tool.</p>
<h2>3. Types of cookies we use</h2>
<p>On the AuditReady website and web application we may use the following basic categories of cookies:</p>
<section>
<h3>3.1 Necessary cookies</h3>
<p>Necessary cookies are required for the basic functioning of the website and web application. Without these cookies, some parts of the service may not work correctly. These cookies are used, for example, to ensure security, manage logins, store cookie settings, protect against misuse and ensure the technical operation of the service.</p>
</section>
<section>
<h3>3.2 Analytics cookies</h3>
<p>Analytics cookies help us understand how users interact with the website, which parts of the site are being visited and how the service can be improved. We use analytics cookies only on the basis of the user’s consent.</p>
</section>
<section>
<h3>3.3 Marketing cookies</h3>
<p>Marketing cookies may be used to measure the effectiveness of campaigns, evaluate conversions or display more relevant content. We use marketing cookies only on the basis of the user’s consent. If marketing cookies are not currently in use, this category will be listed in the cookie settings as unused or will not be active.</p>
</section>
<section>
<h3>3.4 Preference cookies</h3>
<p>Preference cookies may be used to remember user choices, such as language settings, chosen display options or other user preferences. Where these cookies are necessary for the functioning of the service or for storing the user’s choice, they may be included among the necessary cookies. Where they serve only to make use of the website more convenient, they may be used according to the user’s consent settings.</p>
</section>
<h2>4. Necessary cookies</h2>
<p>We use necessary cookies so that the AuditReady website and web application can function correctly and securely. These cookies are usually set in response to an action by the user, such as logging in, submitting a form, configuring cookie preferences or using a secured part of the application.</p>
<p>Necessary cookies may serve in particular the following purposes:</p>
<ul>
<li>ensuring the basic functioning of the website and the application,</li>
<li>managing the user session and login,</li>
<li>protecting against unauthorised access and misuse of the service,</li>
<li>storing cookie consent settings,</li>
<li>security protection of forms and the user account,</li>
<li>technical operation of the service.</li>
</ul>
<p>The use of necessary cookies is not subject to user consent, as they are required for the provision of the service or to ensure its secure operation. The user may disable them in the browser settings, but in that case the website or the web application may not function correctly.</p>
<h2>5. Analytics cookies</h2>
<p>Analytics cookies may be used to measure website traffic, evaluate the use of the site, improve content, optimise the user experience and determine whether the website and its individual parts are clear and effective for users.</p>
<p>We use analytics cookies only if the user grants consent through the cookie banner or another consent management tool. If the user does not grant consent or later withdraws it, analytics cookies will not be actively used.</p>
<p>Analytics tools may process in particular information about the website visit, such as pages visited, duration of the visit, technical information about the device and browser, approximate location derived from the IP address or information about the source from which the user reached the website.</p>
<p>The specific analytics tool and specific cookies will be added in line with the actual implementation of the website. If analytics cookies are used, they will be listed in the overview of cookies used or directly in the cookie banner settings.</p>
<h2>6. Marketing cookies</h2>
<p>Marketing cookies may be used to measure the effectiveness of marketing campaigns, evaluate conversions, manage advertising campaigns or display more relevant content to users.</p>
<p>We use marketing cookies only on the basis of the user’s consent. The user can refuse, change or withdraw consent to marketing cookies at any time through the cookie settings.</p>
<p>In the first version of the AuditReady website or service, marketing cookies may not be in use. If marketing cookies are not in use, this category will not be active or will be marked as unused in the cookie banner.</p>
<p>If marketing cookies are deployed in the future, the overview of cookies used will be updated to include the cookie name, provider, purpose and retention period.</p>
<h2>7. Cookie consent management</h2>
<p>On the first visit to the website, the user may be shown a cookie banner that allows them to decide about the use of optional cookies.</p>
<p>The cookie banner should in particular allow the user to:</p>
<ul>
<li>accept all optional cookies,</li>
<li>reject all optional cookies,</li>
<li>configure individual categories of cookies as the user prefers.</li>
</ul>
<p>Necessary cookies cannot be disabled through the cookie banner because they are required for the functioning of the website or the web application. Analytics and marketing cookies are used only if the user grants consent for them.</p>
<p>The user can change or withdraw their consent at any time through the "Cookie settings" link, which should be available on the website, for example in the website footer.</p>
<p>Rejecting optional cookies does not affect the ability to use the AuditReady website or service, but it may affect some additional features, traffic measurement, content optimisation or campaign evaluation.</p>
<h2>8. Overview of cookies used</h2>
<p>Below is the current overview of cookies and similar technologies that may be used on the AuditReady website or web application according to the current technical implementation. The overview will be updated from time to time if the technologies, analytics or marketing tools used change.</p>
<div class="table-wrap"><table><thead><tr><th>Cookie / technology name</th><th>Category</th><th>Provider</th><th>Purpose</th></tr></thead><tbody><tr><td>auditready_consent</td><td>Preference</td><td>AuditReady</td><td>Stores cookie consent settings and preferences.</td></tr><tr><td>checklist_access_token</td><td>Necessary</td><td>AuditReady</td><td>Used for user login and session management.</td></tr><tr><td>mfa_challenge_token</td><td>Necessary</td><td>AuditReady</td><td>Used for security protection of forms and the multi-factor authentication (MFA) flow.</td></tr><tr><td>stripe_cookies*</td><td>Marketing</td><td>Stripe</td><td>May be used for campaign measurement, conversions or remarketing where those functions are in use and the user has given consent.</td></tr><tr><td>user_language_preference</td><td>Preference</td><td>AuditReady</td><td>Stores user preferences, such as language settings.</td></tr></tbody><p>* The label "stripe_cookies" is a summary entry. The specific cookies or similar technologies provided by Stripe may differ depending on the current implementation of payment, conversion or marketing features.</p></table></div>
<p>Before launching the website and on every significant change to the application, we recommend a technical review of the cookies actually in use. The overview must match what is actually deployed on the website and in the web application. Marketing cookies and related measurement are used only to the extent that matches the user’s consent.</p>
<h2>9. Cookie settings in the browser</h2>
<p>The user can also manage cookies through the settings of their internet browser. In the browser, it is usually possible to block or delete cookies or to set rules for storing them.</p>
<p>If the user disables all cookies in the browser settings, some parts of the AuditReady website or web application may not work or may be limited. This may in particular affect login, secured parts of the application, storage of preferences or the correct functioning of forms.</p>
<p>Browser cookie settings are independent of consent settings managed through the cookie banner. Withdrawing consent in the cookie banner applies to the use of optional cookies by the AuditReady website, while browser settings may technically affect the storage of cookies in general.</p>
<h2>10. Changes to this policy</h2>
<p>We may update this cookie policy from time to time, in particular in connection with changes to the website, the web application, the technologies used, the analytics or marketing tools used, legal requirements or suppliers.</p>
<p>The current version of this policy will always be available on the AuditReady website. If there is a material change in the use of cookies, we may also inform the user through the cookie banner, a notice on the website or in another appropriate manner.</p>
<p>Changes to this policy take effect on the date of their publication, unless stated otherwise.</p>
<h2>11. Contact details</h2>
<p>If you have any questions regarding the use of cookies, consent settings or the processing of personal data, you can contact us at the address below:</p>
<aside>
<h2>AuditReady s.r.o.</h2>
<p>Francouzská 312/100</p>
<p>Vršovice, 101 00 Prague 10</p>
<p>E-mail: info@auditready.cz</p>
</aside>
"""
)

TERMS_OF_SERVICE_HTML_CS = _load_legal_html(
    "AuditReady_Terms_of_Service.html",
    _format_fallback_html(
        "Podmínky služby",
        "Obsah obchodních podmínek bude doplněn.",
    ),
)

TERMS_OF_SERVICE_HTML_EN = _load_legal_html(
    "AuditReady_Terms_of_Service_en.html",
    _format_fallback_html(
        "Terms of Service",
        "Terms of Service content will be added here.",
    ),
)

# Page content data structure - comprehensive content from all frontend pages
PAGES_DATA = {
     "home": {
        "en": {
            "title": "Home",
            "meta_description": "AuditReady - Simplify your cybersecurity audit preparation",
            "status": "published",
            "content_type": "hero",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Built by cybersecurity professionals",
                        "subtitle": "cybersecurity",
                        "accent": "professionals.",
                        "description": "We simplify audit preparation for today's cybersecurity challenges. Our mission is to give security and compliance teams clarity, structure, and confidence - without the complexity.",
                        "kicker": "About Us",
                        "background_image": "/assets/cybersecurity-background-59ognpsy7izka4l9.png",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklists": "Checklists",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "dashboard": {
                                "title": "Dashboard",
                                "metrics": {
                                    "overallReadiness": {
                                        "label": "Overall Readiness",
                                        "value": "72%",
                                        "progress": "72%"
                                    },
                                    "completed": {
                                        "label": "Completed",
                                        "value": "18/25",
                                        "progress": "72%"
                                    },
                                    "openFindings": {
                                        "label": "Open Findings",
                                        "value": "7",
                                        "progress": "28%"
                                    }
                                },
                                "activity": {
                                    "title": "Recent Activity",
                                    "items": [
                                        "Audit Readiness Checklist",
                                        "Documentation Package",
                                        "NIS2 Gap Analysis"
                                    ]
                                },
                                "domains": {
                                    "title": "Top Domains",
                                    "items": [
                                        "Governance",
                                        "Risk Management",
                                        "Access Control"
                                    ],
                                    "current": "Current",
                                    "target": "Target"
                                }
                            }
                        }
                    }
                },
                {
                    "section_type": "cards",
                    "order": 2,
                    "data": {
                        "title": "What We Do",
                        "cards": [
                            {
                                "title": "What We Do",
                                "content": "We are cybersecurity professionals with hands-on experience in audits, compliance, and incident response. Over the years, we have worked with organizations across different industries, helping them strengthen their security and prepare for audits with confidence."
                            },
                            {
                                "title": "Our Experience",
                                "points": [
                                    "Cybersecurity and audit expertise",
                                    "ISO 27001, NIS2, and relevant requirements under the Czech Cybersecurity Act",
                                    "Security assessments and incident response",
                                    "Real-world experience across multiple industries"
                                ]
                            },
                            {
                                "title": "Why This Product Exists",
                                "content": "We saw that many organizations were unprepared not because of lack of effort, but because of unclear requirements, missing documentation, and the lack of a structured approach. Existing tools were either too complex or not focused on what really matters during an audit.<br /><strong>AuditReady was created to change that.</strong>"
                            },
                            {
                                "title": "Our Approach",
                                "content": "We believe audit preparation should be practical, clear, and evidence-based. That's why we built a solution that focuses on what really matters and guides you step by step.",
                                "points": [
                                    "Practical, not theoretical",
                                    "Focused on real audit readiness",
                                    "Evidence-based approach",
                                    "Simple and structured workflow"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Trust & Credentials",
                        "subtitle": "We combine real-world experience with recognized knowledge and standards.",
                        "cards": [
                            {
                                "title": "Real-World Experience",
                                "content": "Years of hands-on work with audits, security assessments, and incident response."
                            },
                            {
                                "title": "Certifications",
                                "content": "Industry-recognized certifications including CISSP, CySA+, and ISO 27001 Lead Auditor."
                            },
                            {
                                "title": "Security Standards",
                                "content": "Deep knowledge of frameworks such as NIS2, ISO 27001, and other international standards."
                            },
                            {
                                "title": "Practical Partnerships",
                                "content": "Collaboration with organizations to strengthen their security and achieve compliance goals."
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Want to know more about our work?",
                        "subtitle": "We're always open to new conversations about how we can help you and your organization stay secure and audit-ready.",
                        "buttons": [
                            {
                                "text": "Contact Us",
                                "url": "/contact",
                                "primary": True
                            },
                            {
                                "text": "Explore Products",
                                "url": "/products",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        },
        "cs": {
            "title": "Domů",
            "meta_description": "AuditReady - Zjednodušte si přípravu na kybernetický audit",
            "status": "published",
            "content_type": "hero",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Vytvořeno\nodborníky na\nkybernetickou bezpečnost.",
                        "subtitle": "kybernetická",
                        "accent": "bezpečnost.",
                        "description": "Pomáháme organizacím rychle zjistit, co je skutečně připravené na audit a co zatím chybí. AuditReady přináší bezpečnostním a compliance týmům přehled, strukturu a jistotu v tom, co lze doložit, kde jsou mezery a na co se zaměřit před dalším auditem.",
                        "kicker": "O nás",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Přehled",
                                "checklists": "Checklisty",
                                "reports": "Reporty",
                                "settings": "Nastavení"
                            },
                            "dashboard": {
                                "title": "Přehled",
                                "metrics": {
                                    "overallReadiness": "Celková připravenost",
                                    "completed": "Dokončeno",
                                    "openFindings": "Otevřená zjištění"
                                },
                                "overallReadiness": {
                                    "value": "72%",
                                    "progress": "72%"
                                },
                                "completed": {
                                    "value": "18/25",
                                    "progress": "72%"
                                },
                                "openFindings": {
                                    "value": "7",
                                    "progress": "28%"
                                }
                            },
                            "activity": {
                                "title": "Poslední aktivita",
                                "items": [
                                    "Audit Readiness Checklist",
                                    "Balíček dokumentace",
                                    "NIS2 gap analýza"
                                ]
                            },
                            "domains": {
                                "title": "Klíčové oblasti",
                                "current": "Aktuálně",
                                "target": "Cíl"
                            }
                        }
                    }
                },
                {
                    "section_type": "cards",
                    "order": 2,
                    "data": {
                        "title": "Co děláme",
                        "cards": [
                            {
                                "title": "Co děláme",
                                "content": "Pomáháme organizacím zhodnotit, v jakém stavu je jejich kybernetická bezpečnost a co je v praxi skutečně připravené.\nVycházíme ze zkušeností z auditů a řízení bezpečnosti napříč různými organizacemi a zaměřujeme se na to, co dává smysl v reálném provozu.\nSoustředíme se na to, aby bezpečnost nebyla jen deklarovaná, ale také skutečně doložitelná."
                            },
                            {
                                "title": "Naše zkušenosti",
                                "points": [
                                    "Odbornost v oblasti kybernetické bezpečnosti a auditní přípravy",
                                    "Praktická zkušenost s požadavky zákona o kybernetické bezpečnosti a navazujících vyhlášek",
                                    "Znalost rámců a standardů, jako jsou ISO 27001 a NIST",
                                    "Praxe z veřejného i soukromého sektoru"
                                ]
                            },
                            {
                                "title": "Proč to děláme",
                                "content": "Pomáháme oddělit formální deklarace od skutečného stavu a ukázat, co organizace dokáže při kontrole doložit.<br /><strong>AuditReady vzniklo proto, aby to celé bylo jednodušší a srozumitelné.</strong>"
                            },
                            {
                                "title": "Jak pracujeme",
                                "content": "Pomáháme organizacím zlepšovat bezpečnost a připravit se na audit bez zbytečné složitosti.",
                                "points": [
                                    "Prakticky, ne teoreticky",
                                    "Zaměřeno na skutečnou auditní připravenost",
                                    "Doložitelnost a evidence",
                                    "Jednoduchý a strukturovaný postup"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Proč nám můžete věřit",
                        "subtitle": "Stavíme na praktických zkušenostech, odborných znalostech a ověřených standardech.",
                        "cards": [
                            {
                                "title": "Zkušenosti z praxe",
                                "content": "Pomáháme oddělit formální deklarace od skutečného stavu a ukázat, co organizace dokáže při kontrole doložit."
                            },
                            {
                                "title": "Certifikace",
                                "content": "Disponujeme odbornými certifikacemi v oblasti kybernetické bezpečnosti a auditu, včetně CISSP, CISA a ISO 27001 Lead Auditor."
                            },
                            {
                                "title": "Standardy a metodiky",
                                "content": "Opíráme se o ISO 27001, NIST frameworky, ITIL, TOGAF a další osvědčené přístupy pro řízení bezpečnosti, IT služeb a architektury."
                            },
                            {
                                "title": "Spolupráce s organizacemi",
                                "content": "Pomáháme organizacím zlepšovat bezpečnost a připravit se na audit bez zbytečné složitosti."
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Chcete vědět víc o tom, jak pracujeme?",
                        "subtitle": "Jsme připraveni probrat, jak můžeme vaší organizaci pomoci lépe vyhodnotit stav kybernetické bezpečnosti a podpořit přípravu na audit nebo interní kontrolu.",
                        "buttons": [
                            {
                                "text": "Kontaktujte nás",
                                "url": "/contact",
                                "primary": True
                            },
                            {
                                "text": "Zobrazit produkty",
                                "url": "/products",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        }
    },
    "about-us": {
        "en": {
            "title": "About Us",
            "meta_description": "Learn about our mission to help organizations achieve audit readiness",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Built by cybersecurity professionals",
                        "subtitle": "cybersecurity",
                        "accent": "professionals.",
                        "description": "We simplify audit preparation for today's cybersecurity challenges. Our mission is to give security and compliance teams clarity, structure, and confidence - without complexity.",
                        "kicker": "About Us",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklists": "Checklists",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "dashboard": {
                                "title": "Dashboard",
                                "metrics": {
                                    "overallReadiness": "Overall Readiness",
                                    "completed": "Completed",
                                    "openFindings": "Open Findings"
                                },
                                "activity": {
                                    "title": "Recent Activity",
                                    "items": [
                                        "Audit Readiness Checklist",
                                        "Documentation Package",
                                        "NIS2 Gap Analysis"
                                    ]
                                },
                                "domains": {
                                    "title": "Top Domains",
                                    "governance": "Governance",
                                    "risk": "Risk",
                                    "management": "Management",
                                    "access": "Access",
                                    "control": "Control",
                                    "asset": "Asset",
                                    "assetManagement": "Management",
                                    "incident": "Incident",
                                    "incidentManagement": "Management"
                                }
                            }
                        }
                    }
                },
                {
                    "section_type": "cards",
                    "order": 2,
                    "data": {
                        "title": "What We Do",
                        "cards": [
                            {
                                "title": "What We Do",
                                "content": "We are cybersecurity professionals with hands-on experience in audits, compliance, and incident response. Over the years, we have worked with organizations across different industries, helping them strengthen their security and prepare for audits with confidence.",
                                "icon": "users"
                            },
                            {
                                "title": "Our Experience",
                                "points": [
                                    "Cybersecurity and audit expertise",
                                    "ISO 27001, NIS2, and relevant requirements under Czech Cybersecurity Act",
                                    "Security assessments and incident response",
                                    "Real-world experience across multiple industries"
                                ],
                                "icon": "check"
                            },
                            {
                                "title": "Why This Product Exists",
                                "content": "We saw that many organizations were unprepared not because of lack of effort, but because of unclear requirements, missing documentation, and lack of a structured approach. Existing tools were either too complex or not focused on what really matters during an audit.",
                                "highlight": "AuditReady was created to change that.",
                                "icon": "lightbulb"
                            },
                            {
                                "title": "Our Approach",
                                "content": "We believe audit preparation should be practical, clear, and evidence-based. That's why we built a solution that focuses on what really matters and guides you step by step.",
                                "points": [
                                    "Practical, not theoretical",
                                    "Focused on real audit readiness",
                                    "Evidence-based approach",
                                    "Simple and structured workflow"
                                ],
                                "icon": "target"
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Trust & Credentials",
                        "subtitle": "We combine real-world experience with recognized knowledge and standards.",
                        "cards": [
                            {
                                "title": "Real-World Experience",
                                "content": "Years of hands-on work with audits, security assessments, and incident response.",
                                "icon": "document"
                            },
                            {
                                "title": "Certifications",
                                "content": "Industry-recognized certifications including CISSP, CySA+, and ISO 27001 Lead Auditor.",
                                "icon": "graduation"
                            },
                            {
                                "title": "Security Standards",
                                "content": "Deep knowledge of frameworks such as NIS2, ISO 27001, and other international standards.",
                                "icon": "shield"
                            },
                            {
                                "title": "Practical Partnerships",
                                "content": "Collaboration with organizations to strengthen their security and achieve compliance goals.",
                                "icon": "handshake"
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Want to know more about our work?",
                        "subtitle": "We're always open to new conversations about how we can help you and your organization stay secure and audit-ready.",
                        "buttons": [
                            {
                                "text": "Contact Us",
                                "url": "/contact",
                                "primary": True
                            },
                            {
                                "text": "Explore Products",
                                "url": "/products",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        },
        "cs": {
            "title": "O nás",
            "meta_description": "Zjistěte více o naší misi pomáhat organizacím dosáhnout připravenosti na audit",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Vytvořeno",
                        "subtitle": "odborníky na",
                        "accent": "kybernetickou bezpečnost.",
                        "description": "Pomáháme organizacím rychle zjistit, co je skutečně připravené na audit a co zatím chybí. AuditReady přináší bezpečnostním a compliance týmům přehled, strukturu a jistotu v tom, co lze doložit, kde jsou mezery a na co se zaměřit před dalším auditem.",
                        "kicker": "O nás",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Přehled",
                                "checklists": "Checklisty",
                                "reports": "Reporty",
                                "settings": "Nastavení"
                            },
                            "dashboard": {
                                "title": "Přehled",
                                "metrics": {
                                    "overallReadiness": "Celková připravenost",
                                    "completed": "Dokončeno",
                                    "openFindings": "Otevřená zjištění"
                                },
                                "activity": {
                                    "title": "Poslední aktivita",
                                    "items": [
                                        "Audit Readiness Checklist",
                                        "Balíček dokumentace",
                                        "NIS2 gap analýza"
                                    ]
                                },
                                "domains": {
                                    "title": "Klíčové oblasti",
                                    "governance": "Governance",
                                    "risk": "Řízení",
                                    "management": "rizik",
                                    "access": "Řízení",
                                    "control": "přístupu",
                                    "asset": "Správa",
                                    "assetManagement": "aktiv",
                                    "incident": "Řízení",
                                    "incidentManagement": "incidentů"
                                }
                            }
                        }
                    }
                },
                {
                    "section_type": "cards",
                    "order": 2,
                    "data": {
                        "title": "Co děláme",
                        "cards": [
                            {
                                "title": "Co děláme",
                                "content": "Pomáháme organizacím zhodnotit, v jakém stavu je jejich kybernetická bezpečnost a co je v praxi skutečně připravené. Vycházíme ze zkušeností z auditů a řízení bezpečnosti napříč různými organizacemi a zaměřujeme se na to, co dává smysl v reálném provozu. Soustředíme se na to, aby bezpečnost nebyla jen deklarovaná, ale také skutečně doložitelná.",
                                "icon": "users"
                            },
                            {
                                "title": "Naše zkušenosti",
                                "points": [
                                    "Odbornost v oblasti kybernetické bezpečnosti a auditní přípravy",
                                    "Praktická zkušenost s požadavky zákona o kybernetické bezpečnosti a navazujících vyhlášek",
                                    "Znalost rámců a standardů, jako jsou ISO 27001 a NIST",
                                    "Praxe z veřejného i soukromého sektoru"
                                ],
                                "icon": "check"
                            },
                            {
                                "title": "Proč to děláme",
                                "content": "Pomáháme oddělit formální deklarace od skutečného stavu a ukázat, co organizace dokáže při kontrole doložit.",
                                "highlight": "AuditReady vzniklo proto, aby to celé bylo jednodušší a srozumitelné.",
                                "icon": "lightbulb"
                            },
                            {
                                "title": "Jak pracujeme",
                                "content": "Pomáháme organizacím zlepšovat bezpečnost a připravit se na audit bez zbytečné složitosti.",
                                "points": [
                                    "Prakticky, ne teoreticky",
                                    "Zaměřeno na skutečnou auditní připravenost",
                                    "Doložitelnost a evidence",
                                    "Jednoduchý a strukturovaný postup"
                                ],
                                "icon": "target"
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Proč nám můžete věřit",
                        "subtitle": "Stavíme na praktických zkušenostech, odborných znalostech a ověřených standardech.",
                        "cards": [
                            {
                                "title": "Zkušenosti z praxe",
                                "content": "Pomáháme oddělit formální deklarace od skutečného stavu a ukázat, co organizace dokáže při kontrole doložit.",
                                "icon": "document"
                            },
                            {
                                "title": "Certifikace",
                                "content": "Disponujeme odbornými certifikacemi v oblasti kybernetické bezpečnosti a auditu, včetně CISSP, CISA a ISO 27001 Lead Auditor.",
                                "icon": "graduation"
                            },
                            {
                                "title": "Standardy a metodiky",
                                "content": "Opíráme se o ISO 27001, NIST frameworky, ITIL, TOGAF a další osvědčené přístupy pro řízení bezpečnosti, IT služeb a architektury.",
                                "icon": "shield"
                            },
                            {
                                "title": "Spolupráce s organizacemi",
                                "content": "Pomáháme organizacím zlepšovat bezpečnost a připravit se na audit bez zbytečné složitosti.",
                                "icon": "handshake"
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Chcete vědět víc o tom, jak pracujeme?",
                        "subtitle": "Jsme připraveni probrat, jak můžeme vaší organizaci pomoci lépe vyhodnotit stav kybernetické bezpečnosti a podpořit přípravu na audit nebo interní kontrolu.",
                        "buttons": [
                            {
                                "text": "Kontaktujte nás",
                                "url": "/contact",
                                "primary": True
                            },
                            {
                                "text": "Zobrazit produkty",
                                "url": "/products",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        }
    },
    "contact": {
        "en": {
            "title": "Contact Us",
            "meta_description": "Get in touch with our team for support and inquiries",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Contact Us",
                        "subtitle": "Have a question about audit readiness or the product?",
                        "kicker": "Contact Us",
                        "form": {
                            "name": "Name",
                            "email": "Email",
                            "company": "Company (optional)",
                            "message": "Message",
                            "messagePlaceholder": "Describe your situation (e.g., upcoming audit, missing documentation, unclear requirements)",
                            "sendButton": "Send Message"
                        },
                        "directContact": {
                            "title": "Prefer direct contact?",
                            "subtitle": "Feel free to email us anytime.",
                            "email": "info@checklistkb.com",
                            "responseTime": "We respond within 24 hours."
                        }
                    }
                },
                {
                    "section_type": "cta",
                    "order": 2,
                    "data": {
                        "title": "Start your assessment today",
                        "subtitle": "Get access to our tools and simplify your cybersecurity audit process.",
                        "buttons": [
                            {
                                "text": "Get Access",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "View Products",
                                "url": "/products/audit-readiness-checklist",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        },
        "cs": {
            "title": "Kontaktujte nás",
            "meta_description": "Kontaktujte náš tým pro podporu a dotazy",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Kontaktujte nás",
                        "subtitle": "Máte dotaz k auditní připravenosti nebo k produktu?",
                        "kicker": "Kontaktujte nás",
                        "form": {
                            "name": "Jméno",
                            "email": "E-mail",
                            "company": "Společnost (volitelné)",
                            "message": "Zpráva",
                            "messagePlaceholder": "Popište svou situaci (např. blížící se audit, chybějící dokumentace, nejasné požadavky)",
                            "sendButton": "Odeslat zprávu"
                        },
                        "directContact": {
                            "title": "Preferujete přímý kontakt?",
                            "subtitle": "Napište nám kdykoliv e-mailem.",
                            "email": "info@checklistkb.com",
                            "responseTime": "Odpovídáme do 24 hodin."
                        }
                    }
                },
                {
                    "section_type": "cta",
                    "order": 2,
                    "data": {
                        "title": "Začněte s hodnocením ještě dnes",
                        "subtitle": "Získejte přístup k našim nástrojům a zjednodušte audit kybernetické bezpečnosti.",
                        "buttons": [
                            {
                                "text": "Získat přístup",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "Zobrazit produkty",
                                "url": "/products/audit-readiness-checklist",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        }
    },
    "faq": {
        "en": {
            "title": "Frequently Asked Questions",
            "meta_description": "Find answers to common questions about our platform",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Frequently Asked Questions",
                        "subtitle": "Everything you need to know about access, assessments, reports, and platform security.",
                        "kicker": "Help center"
                    }
                },
                {
                    "section_type": "faq",
                    "order": 2,
                    "data": {
                        "title": "Quick Answers",
                        "subtitle": "Click a question to expand details.",
                        "items": [
                            {
                                "question": "When does my 7-day window begin?",
                                "answer": "The 7-day completion window starts only when you click Start Assessment, not immediately after payment."
                            },
                            {
                                "question": "Is evidence upload mandatory?",
                                "answer": "No. Uploads are optional, but recommended to support auditor review and report quality."
                            },
                            {
                                "question": "How is access unlocked after payment?",
                                "answer": "Access is unlocked automatically after Stripe webhook confirmation is processed by the backend."
                            },
                            {
                                "question": "Which roles are supported?",
                                "answer": "The platform supports admin/operator, read-only auditor, and customer roles."
                            },
                            {
                                "question": "Can I save progress and continue later?",
                                "answer": "Yes. Your assessment progress is saved so you can continue within your active access window."
                            },
                            {
                                "question": "How do I get my final report?",
                                "answer": "After completing the checklist, your report is available in the Reports area for download and sharing."
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 3,
                    "data": {
                        "title": "Still have questions?",
                        "subtitle": "Reach out and we'll help you get the answers you need.",
                        "buttons": [
                            {
                                "text": "Contact Us",
                                "url": "/contact",
                                "primary": True
                            }
                        ]
                    }
                }
            ]
        },
        "cs": {
            "title": "Často kladené otázky",
            "meta_description": "Najděte odpovědi na běžné otázky o naší platformě",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Často kladené otázky",
                        "subtitle": "Vše, co potřebujete vědět o přístupu, hodnocení, reportech a bezpečnosti platformy.",
                        "kicker": "Centrum nápovědy"
                    }
                },
                {
                    "section_type": "faq",
                    "order": 2,
                    "data": {
                        "title": "Rychlé odpovědi",
                        "subtitle": "Kliknutím na otázku zobrazíte detail.",
                        "items": [
                            {
                                "question": "Kdy začíná 7denní období?",
                                "answer": "Sedmidenní okno začíná až ve chvíli, kdy kliknete na 'Start Assessment', ne hned po platbě."
                            },
                            {
                                "question": "Je nahrání důkazů povinné?",
                                "answer": "Ne. Nahrávání je volitelné, ale doporučené pro podporu auditorova ověření a kvality reportu."
                            },
                            {
                                "question": "Jak se po zaplacení odemkne přístup?",
                                "answer": "Přístup se odemkne automaticky po zpracování potvrzení webhooks ze Stripe na backendu."
                            },
                            {
                                "question": "Jaké role jsou podporované?",
                                "answer": "Platforma podporuje role admin/operator, auditor pouze pro čtení a zákaznické role."
                            },
                            {
                                "question": "Mohu si uložit postup a pokračovat později?",
                                "answer": "Ano. Průběh hodnocení se ukládá, takže můžete pokračovat v rámci aktivního přístupového okna."
                            },
                            {
                                "question": "Jak získám finální report?",
                                "answer": "Po dokončení checklistu je report dostupný v části Reports pro stažení a sdílení."
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 3,
                    "data": {
                        "title": "Máte další otázky?",
                        "subtitle": "Napište nám a pomůžeme vám získat odpovědi, které potřebujete.",
                        "buttons": [
                            {
                                "text": "Kontaktujte nás",
                                "url": "/contact",
                                "primary": True
                            }
                        ]
                    }
                }
            ]
        }
    },
    "products": {
        "en": {
            "title": "Products",
            "meta_description": "Explore our suite of audit readiness solutions",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Close Gaps. Save Time.",
                        "subtitle": "Get Expert-Ready",
                        "accent": "Documentation.",
                        "description": "Buy individual policy sections with ready-to-use templates, guidelines, and admin instructions - written by security experts, aligned to ISO 27001, NIS2, and best practices.",
                        "kicker": "Documentation blueprints",
                        "highlights": [
                            {
                                "title": "Audit-ready",
                                "body": "Aligned to frameworks"
                            },
                            {
                                "title": "Instant delivery",
                                "body": "Download and use"
                            },
                            {
                                "title": "Expert written",
                                "body": "Practical. Clear. Complete."
                            }
                        ],
                        "mockup": {
                            "brand": "AuditReady",
                            "library": "Documentation Library",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklist": "Checklist",
                                "evidence": "Evidence",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "documents": [
                                "Mobile Device Policy",
                                "Access Control Policy",
                                "Incident Response Policy",
                                "Data Classification Policy"
                            ]
                        }
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 2,
                    "data": {
                        "title": "How it works",
                        "subtitle": "Find section you need. Download. Customize. Stay compliant.",
                        "steps": [
                            {
                                "title": "1. Find Gap",
                                "body": "Your assessment shows what's missing."
                            },
                            {
                                "title": "2. Choose a Section",
                                "body": "Pick policy section you need."
                            },
                            {
                                "title": "3. Download Instantly",
                                "body": "Get documents in PDF and DOCX."
                            },
                            {
                                "title": "4. Customize & Use",
                                "body": "Adapt to your organization. You're ready."
                            }
                        ]
                    }
                },
                {
                    "section_type": "documentation-grid",
                    "order": 3,
                    "data": {
                        "title": "Browse Documentation Sections",
                        "subtitle": "Each section includes a policy, user guidelines, and admin guidelines.",
                        "categories": [
                            "All",
                            "Access & Identity",
                            "Devices & Endpoints",
                            "Data Protection",
                            "Operations",
                            "Governance",
                            "Response"
                        ],
                        "documents": [
                            {
                                "id": "mobileDevice",
                                "name": "Mobile Device Policy",
                                "subtitle": "Define rules for corporate and personal mobile devices.",
                                "price": "€149",
                                "category": "Devices & Endpoints",
                                "badge": "Popular",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            },
                            {
                                "id": "remoteWork",
                                "name": "Remote Work Policy",
                                "subtitle": "Secure and productive remote work, clearly defined.",
                                "price": "€149",
                                "category": "Operations",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            },
                            {
                                "id": "accessControl",
                                "name": "Access Control Policy",
                                "subtitle": "Manage who has access to what, and under which conditions.",
                                "price": "€179",
                                "category": "Access & Identity",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines",
                                    "Admin Guidelines (Advanced)"
                                ]
                            },
                            {
                                "id": "incidentResponse",
                                "name": "Incident Response Policy",
                                "subtitle": "Be ready when incidents happen. Act fast. Act right.",
                                "price": "€199",
                                "category": "Response",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines",
                                    "Response Playbooks"
                                ]
                            },
                            {
                                "id": "dataClassification",
                                "name": "Data Classification Policy",
                                "subtitle": "Define how data is labeled, handled, and protected.",
                                "price": "€149",
                                "category": "Data Protection",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            },
                            {
                                "id": "securityGovernance",
                                "name": "Security Governance Policy",
                                "subtitle": "Roles, accountability, and oversight for your information security program.",
                                "price": "€189",
                                "category": "Governance",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "bundles",
                    "order": 4,
                    "data": {
                        "title": "Bundle & Save",
                        "subtitle": "Get multiple sections and save up to 25%.",
                        "bundles": [
                            {
                                "title": "Essential Bundle",
                                "subtitle": "3 sections of your choice",
                                "price": "€399",
                                "originalPrice": "€447",
                                "save": "Save 10%"
                            },
                            {
                                "title": "Professional Bundle",
                                "subtitle": "5 sections of your choice",
                                "price": "€599",
                                "originalPrice": "€745",
                                "save": "Save 20%",
                                "badge": "Most Popular"
                            },
                            {
                                "title": "Complete Bundle",
                                "subtitle": "10 sections of your choice",
                                "price": "€999",
                                "originalPrice": "€1,490",
                                "save": "Save 25%"
                            }
                        ]
                    }
                },
                {
                    "section_type": "why-choose",
                    "order": 5,
                    "data": {
                        "title": "Why organizations choose our documentation",
                        "points": [
                            "Written by cybersecurity experts",
                            "Aligned to ISO 27001, NIS2 and best practices",
                            "Ready to customize and use",
                            "Saves weeks of manual work",
                            "Used by auditors and security teams"
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 6,
                    "data": {
                        "title": "Found a gap. Now close it.",
                        "subtitle": "Get right documentation section and move forward with confidence.",
                        "buttons": [
                            {
                                "text": "View product details",
                                "url": "/products/audit-readiness-checklist"
                            },
                            {
                                "text": "Create account",
                                "url": "/register"
                            }
                        ]
                    }
                }
            ]
        },
        "cs": {
            "title": "Produkty",
            "meta_description": "Prozkoumejte naši sadu řešení pro připravenost na audit",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Uzavřete mezery. Ušetřete čas.",
                        "subtitle": "Získejte dokumentaci",
                        "accent": "připravenou pro audit.",
                        "description": "Kupte jednotlivé části zásad s připravenými šablonami, doporučeními a admin instrukcemi – napsané bezpečnostními experty, sladěné s ISO 27001, NIS2 a best practices.",
                        "kicker": "Dokumentační šablony",
                        "highlights": [
                            {
                                "title": "Audit-ready",
                                "body": "Sladěno s rámci"
                            },
                            {
                                "title": "Okamžité doručení",
                                "body": "Stáhněte a použijte"
                            },
                            {
                                "title": "Napsané experty",
                                "body": "Praktické. Jasné. Kompletní."
                            }
                        ],
                        "mockup": {
                            "brand": "AuditReady",
                            "library": "Knihovna dokumentace",
                            "nav": {
                                "dashboard": "Přehled",
                                "checklist": "Checklist",
                                "evidence": "Důkazy",
                                "reports": "Reporty",
                                "settings": "Nastavení"
                            },
                            "documents": [
                                "Zásada pro mobilní zařízení",
                                "Zásada řízení přístupu",
                                "Postup reakce na incidenty",
                                "Zásada klasifikace dat"
                            ]
                        }
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 2,
                    "data": {
                        "title": "Jak to funguje",
                        "subtitle": "Najděte potřebnou část. Stáhněte. Upravte. Buďte v souladu.",
                        "steps": [
                            {
                                "title": "1. Najděte mezeru",
                                "body": "Hodnocení ukáže, co chybí."
                            },
                            {
                                "title": "2. Vyberte sekci",
                                "body": "Zvolte část zásady, kterou potřebujete."
                            },
                            {
                                "title": "3. Okamžitě stáhněte",
                                "body": "Získejte dokumenty v PDF a DOCX."
                            },
                            {
                                "title": "4. Upravte a používejte",
                                "body": "Přizpůsobte organizaci. Hotovo."
                            }
                        ]
                    }
                },
                {
                    "section_type": "documentation-grid",
                    "order": 3,
                    "data": {
                        "title": "Procházet sekce dokumentace",
                        "subtitle": "Každá sekce obsahuje zásadu, uživatelské a admin pokyny.",
                        "categories": [
                            "Vše",
                            "Přístup & identita",
                            "Zařízení & endpointy",
                            "Ochrana dat",
                            "Provoz",
                            "Governance",
                            "Reakce"
                        ],
                        "documents": [
                            {
                                "id": "mobileDevice",
                                "name": "Zásada pro mobilní zařízení",
                                "subtitle": "Definuje pravidla pro firemní i soukromá mobilní zařízení.",
                                "price": "€149",
                                "category": "Zařízení & endpointy",
                                "badge": "Oblíbené",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            },
                            {
                                "id": "remoteWork",
                                "name": "Zásada práce na dálku",
                                "subtitle": "Bezpečná a produktivní práce na dálku – jasně definovaná.",
                                "price": "€149",
                                "category": "Provoz",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            },
                            {
                                "id": "accessControl",
                                "name": "Zásada řízení přístupu",
                                "subtitle": "Řiďte, kdo má k čemu přístup a za jakých podmínek.",
                                "price": "€179",
                                "category": "Přístup & identita",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory",
                                    "Pokyny pro administrátory (pokročilé)"
                                ]
                            },
                            {
                                "id": "incidentResponse",
                                "name": "Postup reakce na incidenty",
                                "subtitle": "Buďte připraveni na incidenty. Rychle. Správně.",
                                "price": "€199",
                                "category": "Reakce",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory",
                                    "Incidentní scénáře"
                                ]
                            },
                            {
                                "id": "dataClassification",
                                "name": "Zásada klasifikace dat",
                                "subtitle": "Definuje, jak jsou data označována, zpracovávána a chráněna.",
                                "price": "€149",
                                "category": "Ochrana dat",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            },
                            {
                                "id": "securityGovernance",
                                "name": "Zásada řízení bezpečnosti",
                                "subtitle": "Role, odpovědnosti a dohled nad programem informační bezpečnosti.",
                                "price": "€189",
                                "category": "Governance",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "bundles",
                    "order": 4,
                    "data": {
                        "title": "Balíčky & úspora",
                        "subtitle": "Získejte více sekcí a ušetřete až 25 %.",
                        "bundles": [
                            {
                                "title": "Essential balíček",
                                "subtitle": "3 sekce dle výběru",
                                "price": "€399",
                                "originalPrice": "€447",
                                "save": "Ušetříte 10 %"
                            },
                            {
                                "title": "Professional balíček",
                                "subtitle": "5 sekcí dle výběru",
                                "price": "€599",
                                "originalPrice": "€745",
                                "save": "Ušetříte 20 %",
                                "badge": "Nejoblíbenější"
                            },
                            {
                                "title": "Complete balíček",
                                "subtitle": "10 sekcí dle výběru",
                                "price": "€999",
                                "originalPrice": "€1,490",
                                "save": "Ušetříte 25 %"
                            }
                        ]
                    }
                },
                {
                    "section_type": "why-choose",
                    "order": 5,
                    "data": {
                        "title": "Proč si organizace vybírají naši dokumentaci",
                        "points": [
                            "Napsáno odborníky na kybernetickou bezpečnost",
                            "Sladěno s ISO 27001, NIS2 a best practices",
                            "Připravené k úpravě a okamžitému použití",
                            "Ušetří týdny manuální práce",
                            "Používané auditory i bezpečnostními týmy"
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 6,
                    "data": {
                        "title": "Našli jste mezeru. Teď ji uzavřete.",
                        "subtitle": "Vyberte správnou část dokumentace a posuňte se dál s jistotou.",
                        "buttons": [
                            {
                                "text": "Zobrazit detail produktu",
                                "url": "/products/audit-readiness-checklist"
                            },
                            {
                                "text": "Vytvořit účet",
                                "url": "/register"
                            }
                        ]
                    }
                }
            ]
        }
    },
    "resources-public": {
        "en": {
            "title": "Audit Readiness Checklist",
            "meta_description": "Prepare for audits with confidence. Simplify complex compliance requirements into clear, actionable steps.",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Audit Readiness Checklist",
                        "subtitle": "Prepare for audits with confidence. Simplify complex compliance requirements into clear, actionable steps. Find gaps, upload evidence, and get a reviewed report to prove your readiness.",
                        "badge": "Audit",
                        "highlights": [
                            {
                                "title": "Secure & Private",
                                "body": "Your data stays protected",
                                "icon": "shield"
                            },
                            {
                                "title": "Expert Review",
                                "body": "Every report is reviewed by our team",
                                "icon": "clipboard-check"
                            },
                            {
                                "title": "Fast & Focused",
                                "body": "Start, assess, and finish in just a few days",
                                "icon": "lightning"
                            }
                        ],
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklists": "Checklists",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "sectionTitle": "1.1 Information Security Policies",
                            "question": "Does your organization have documented information security policies?",
                            "questionHelp": "Policies should cover information classification, access control, incident management, and audit practice requirements.",
                            "progress": "Progress",
                            "answers": {
                                "yes": "Yes",
                                "partly": "Partly",
                                "no": "No",
                                "notSure": "Not sure"
                            },
                            "evidence": "Evidence",
                            "maturity": "Maturity Overview",
                            "legend": {
                                "current": "Current",
                                "target": "Target"
                            }
                        }
                    }
                },
                {
                    "section_type": "main-benefit",
                    "order": 2,
                    "data": {
                        "kicker": "Main benefit",
                        "title": "Know exactly how prepared you are for an audit — before the auditor arrives.",
                        "body": "Identify gaps, validate controls, and get a clear path to audit readiness. Reduce risk, save time, and approach your next audit with confidence."
                    }
                },
                {
                    "section_type": "use-cases",
                    "order": 3,
                    "data": {
                        "title": "Use Cases",
                        "items": [
                            {
                                "title": "Before an Audit",
                                "body": "Assess your readiness, close gaps, and avoid surprises during the audit.",
                                "icon": "calendar"
                            },
                            {
                                "title": "Internal Review",
                                "body": "Validate your current security and compliance posture and ensure controls are in place and effective.",
                                "icon": "search"
                            },
                            {
                                "title": "Gap Analysis",
                                "body": "Compare your environment with regulatory requirements, identify weak areas, and prioritize what to fix first.",
                                "icon": "target"
                            },
                            {
                                "title": "Documentation Readiness",
                                "body": "Understand what needs to be documented and prepare policies, procedures, and evidence with confidence.",
                                "icon": "doc-stack"
                            }
                        ]
                    }
                },
                {
                    "section_type": "who-its-for",
                    "order": 4,
                    "data": {
                        "title": "Who it's for",
                        "subtitle": "Built for teams that need to prove security, close gaps, and stay audit-ready.",
                        "items": [
                            {
                                "title": "Compliance & GRC Teams",
                                "body": "Stay on top of frameworks and regulatory requirements.",
                                "icon": "shield-check"
                            },
                            {
                                "title": "IT & Security Teams",
                                "body": "Identify gaps and prioritize what matters most.",
                                "icon": "users"
                            },
                            {
                                "title": "Management",
                                "body": "Get clear insights and prove your organization is prepared.",
                                "icon": "target"
                            },
                            {
                                "title": "Auditors & Consultants",
                                "body": "Save time with structured, consistent assessments.",
                                "icon": "users"
                            }
                        ]
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 5,
                    "data": {
                        "title": "How it works",
                        "subtitle": "A simple 5-step process to go from uncertainty to audit-ready.",
                        "steps": [
                            {
                                "title": "Choose a checklist",
                                "body": "Pick the compliance framework or checklist that matches your organization's needs."
                            },
                            {
                                "title": "Answer guided questions",
                                "body": "We break down requirements into clear, structured questions so you always know what to do."
                            },
                            {
                                "title": "Upload evidence (optional)",
                                "body": "Attach documents, screenshots, or files that support your answers. We accept PDF, PNG, and JPG."
                            },
                            {
                                "title": "Admin review & final report",
                                "body": "Our team reviews your assessment, validates the evidence, and publishes your final report."
                            },
                            {
                                "title": "Assessment data lifecycle",
                                "body": "Your data is securely deleted within 48 hours after completion. You stay in control."
                            }
                        ]
                    }
                },
                {
                    "section_type": "what-you-get",
                    "order": 6,
                    "data": {
                        "title": "What you get",
                        "subtitle": "Clear outputs, practical guidance, and audit-ready results you can use right away.",
                        "cards": [
                            {
                                "title": "Clear Gap Analysis",
                                "body": "See where you stand and what needs improvement before the audit begins.",
                                "tone": "green",
                                "points": [
                                    "Visual maturity overview",
                                    "Section-by-section scoring",
                                    "Easy-to-understand findings"
                                ]
                            },
                            {
                                "title": "Structured Report",
                                "body": "A professional report you can review internally and share with confidence.",
                                "tone": "blue",
                                "points": [
                                    "Executive summary",
                                    "Detailed findings",
                                    "Maturity score and overview"
                                ]
                            },
                            {
                                "title": "Actionable Recommendations",
                                "body": "Know what to fix next, in what order, and where to focus first.",
                                "tone": "amber",
                                "points": [
                                    "Prioritized by risk and impact",
                                    "Practical next steps",
                                    "Built-in guidance for follow-up"
                                ]
                            },
                            {
                                "title": "Stronger Audit Readiness",
                                "body": "Move into your audit with more confidence, clearer evidence, and less uncertainty.",
                                "tone": "purple",
                                "points": [
                                    "Identify gaps early",
                                    "Improve with evidence",
                                    "Save time and reduce stress"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 7,
                    "data": {
                        "title": "Ready to close your gaps and get audit-ready?",
                        "subtitle": "Start your assessment now and see where you stand.",
                        "buttons": [
                            {
                                "text": "Get Access",
                                "href": "/products/audit-readiness",
                                "variant": "primary"
                            },
                            {
                                "text": "View Product",
                                "href": "/products/audit-readiness",
                                "variant": "secondary"
                            }
                        ]
                    }
                }
            ]
        },
        "cs": {
            "title": "Checklist pro auditní připravenost",
            "meta_description": "Připravte se na audit s jistotou. Zjednodušte složité požadavky do jasných a akčních kroků.",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Checklist pro auditní připravenost",
                        "subtitle": "Připravte se na audit s jistotou. Zjednodušte složité požadavky do jasných a akčních kroků. Najděte mezery, nahrajte důkazy a získejte zkontrolovaný report, kterým prokážete připravenost.",
                        "badge": "Audit",
                        "highlights": [
                            {
                                "title": "Bezpečné & soukromé",
                                "body": "Vaše data zůstávají chráněná",
                                "icon": "shield"
                            },
                            {
                                "title": "Odborná kontrola",
                                "body": "Každý report kontroluje náš tým",
                                "icon": "clipboard-check"
                            },
                            {
                                "title": "Rychle & k věci",
                                "body": "Začněte, vyhodnoťte a dokončete během pár dní",
                                "icon": "lightning"
                            }
                        ],
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklists": "Checklists",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "sectionTitle": "1.1 Information Security Policies",
                            "question": "Má vaše organizace zdokumentované zásady bezpečnosti informací?",
                            "questionHelp": "Zásady by měly pokrývat klasifikaci informací, kontrolu přístupu, řízení incidentů a požadavky na auditorské postupy.",
                            "progress": "Pokrok",
                            "answers": {
                                "yes": "Ano",
                                "partly": "Částečně",
                                "no": "Ne",
                                "notSure": "Nejsem si jistý"
                            },
                            "evidence": "Důkazy",
                            "maturity": "Přehled zralosti",
                            "legend": {
                                "current": "Aktuální",
                                "target": "Cíl"
                            }
                        }
                    }
                },
                {
                    "section_type": "main-benefit",
                    "order": 2,
                    "data": {
                        "kicker": "Hlavní přínos",
                        "title": "Získejte jasnou představu o připravenosti na audit — dříve, než auditor dorazí.",
                        "body": "Identifikujte mezery, ověřte kontroly a získejte jasnou cestu k auditní připravenosti. Snižte riziko, ušetřete čas a zvládněte další audit s jistotou."
                    }
                },
                {
                    "section_type": "use-cases",
                    "order": 3,
                    "data": {
                        "title": "Použití",
                        "items": [
                            {
                                "title": "Před auditem",
                                "body": "Zhodnoťte připravenost, uzavřete mezery a vyhněte se překvapením během auditu.",
                                "icon": "calendar"
                            },
                            {
                                "title": "Interní kontrola",
                                "body": "Ověřte aktuální bezpečnostní a compliance stav a ujistěte se, že opatření fungují.",
                                "icon": "search"
                            },
                            {
                                "title": "Gap analýza",
                                "body": "Porovnejte prostředí s požadavky, najděte slabá místa a stanovte priority oprav.",
                                "icon": "target"
                            },
                            {
                                "title": "Připravenost dokumentace",
                                "body": "Získejte jasno, co je potřeba zdokumentovat, a připravte zásady, postupy a důkazy.",
                                "icon": "doc-stack"
                            }
                        ]
                    }
                },
                {
                    "section_type": "who-its-for",
                    "order": 4,
                    "data": {
                        "title": "Pro koho je to",
                        "subtitle": "Vytvořeno pro týmy, které potřebují prokázat bezpečnost, uzavřít mezery a být připravené na audit.",
                        "items": [
                            {
                                "title": "Compliance & GRC týmy",
                                "body": "Mějte přehled o rámcích a regulatorních požadavcích.",
                                "icon": "shield-check"
                            },
                            {
                                "title": "IT & Security týmy",
                                "body": "Identifikujte mezery a stanovte priority toho nejdůležitějšího.",
                                "icon": "users"
                            },
                            {
                                "title": "Vedení",
                                "body": "Získejte jasné informace a prokažte připravenost organizace.",
                                "icon": "target"
                            },
                            {
                                "title": "Auditoři & konzultanti",
                                "body": "Ušetřete čas díky strukturovanému a konzistentnímu hodnocení.",
                                "icon": "users"
                            }
                        ]
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 5,
                    "data": {
                        "title": "Jak to funguje",
                        "subtitle": "Jednoduchý 5krokový proces od nejistoty k auditní připravenosti.",
                        "steps": [
                            {
                                "title": "Vyberte checklist",
                                "body": "Zvolte rámec nebo checklist, který odpovídá potřebám vaší organizace."
                            },
                            {
                                "title": "Odpovězte na vedené otázky",
                                "body": "Požadavky rozkládáme na jasné a strukturované otázky, abyste vždy věděli, co dělat."
                            },
                            {
                                "title": "Nahrajte důkazy (volitelně)",
                                "body": "Přiložte dokumenty, screenshoty nebo soubory k podpoře odpovědí. Podporujeme PDF, PNG a JPG."
                            },
                            {
                                "title": "Kontrola a finální report",
                                "body": "Náš tým ověří hodnocení, zkontroluje důkazy a publikuje finální report."
                            },
                            {
                                "title": "Životní cyklus dat hodnocení",
                                "body": "Vaše data jsou bezpečně smazána do 48 hodin po dokončení. Máte kontrolu."
                            }
                        ]
                    }
                },
                {
                    "section_type": "what-you-get",
                    "order": 6,
                    "data": {
                        "title": "Co získáte",
                        "subtitle": "Jasné výstupy, praktické vedení a audit-ready výsledky, které můžete hned použít.",
                        "cards": [
                            {
                                "title": "Jasná gap analýza",
                                "body": "Uvidíte, kde jste a co je potřeba zlepšit dříve, než audit začne.",
                                "tone": "green",
                                "points": [
                                    "Vizuální přehled zralosti",
                                    "Skóre po jednotlivých sekcích",
                                    "Srozumitelná zjištění"
                                ]
                            },
                            {
                                "title": "Strukturovaný report",
                                "body": "Profesionální report pro interní použití i sdílení s jistotou.",
                                "tone": "blue",
                                "points": [
                                    "Executive summary",
                                    "Detailní zjištění",
                                    "Skóre a přehled zralosti"
                                ]
                            },
                            {
                                "title": "Doporučení k dalším krokům",
                                "body": "Budete vědět, co opravit jako další, v jakém pořadí a na co se zaměřit.",
                                "tone": "amber",
                                "points": [
                                    "Prioritizováno dle rizika a dopadu",
                                    "Praktické další kroky",
                                    "Vedení pro následné kroky"
                                ]
                            },
                            {
                                "title": "Lepší auditní připravenost",
                                "body": "Jděte do auditu s větší jistotou, lepšími důkazy a menší nejistotou.",
                                "tone": "purple",
                                "points": [
                                    "Odhalte mezery včas",
                                    "Zlepšujte s důkazy",
                                    "Ušetřete čas a stres"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 7,
                    "data": {
                        "title": "Chcete uzavřít mezery a být audit-ready?",
                        "subtitle": "Začněte hodnocení a zjistěte, kde jste.",
                        "buttons": [
                            {
                                "text": "Získat přístup",
                                "href": "/products/audit-readiness",
                                "variant": "primary"
                            },
                            {
                                "text": "Zobrazit produkt",
                                "href": "/products/audit-readiness",
                                "variant": "secondary"
                            }
                        ]
                    }
                }
            ]
        }
    },
    "privacy-policy": {
        "en": {
            "title": "Privacy Policy",
            "meta_description": "Read our privacy policy",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Privacy Policy",
                        "content": PRIVACY_POLICY_HTML_EN
                    }
                }
            ]
        },
        "cs": {
            "title": "Zásady ochrany osobních údajů",
            "meta_description": "Přečtěte si naše zásady ochrany osobních údajů",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Zásady ochrany osobních údajů",
                        "content": PRIVACY_POLICY_HTML_CS
                    }
                }
            ]
        }
    },
    "terms-of-service": {
        "en": {
            "title": "Terms of Service",
            "meta_description": "Read our terms of service",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Terms of Service",
                        "content": TERMS_OF_SERVICE_HTML_EN
                    }
                }
            ]
        },
        "cs": {
            "title": "Podmínky služby",
            "meta_description": "Přečtěte si naše podmínky služby",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Podmínky služby",
                        "content": TERMS_OF_SERVICE_HTML_CS
                    }
                }
            ]
        }
    },
    "cookies": {
        "en": {
            "title": "Cookie Policy",
            "meta_description": "Learn about our cookie policy",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Cookie Policy",
                        "content": COOKIE_POLICY_HTML_EN
                    }
                }
            ]
        },
        "cs": {
            "title": "Zásady cookies",
            "meta_description": "Zjistěte více o našich zásadách cookies",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Zásady cookies",
                        "content": COOKIE_POLICY_HTML_CS
                    }
                }
            ]
        }
    },
}

def seed_database():
    """Seed the CMS database with initial content."""
    db: Session = SessionLocal()

    def upsert_page(slug: str, lang: str, page_data: dict, admin_id):
        page = db.query(Page).filter(Page.slug == slug, Page.language == lang).first()
        created = False

        if page is None:
            page = Page(
                id=uuid4(),
                slug=slug,
                language=lang,
                title=page_data["title"],
                meta_description=page_data["meta_description"],
                status=page_data["status"],
                content_type=page_data["content_type"],
                created_by_id=admin_id,
                updated_by_id=admin_id,
            )
            db.add(page)
            db.flush()
            created = True
        else:
            page.title = page_data["title"]
            page.meta_description = page_data["meta_description"]
            page.status = page_data["status"]
            page.content_type = page_data["content_type"]
            page.updated_by_id = admin_id
            db.query(PageSection).filter(PageSection.page_id == page.id).delete(synchronize_session=False)

        for section_data in page_data["sections"]:
            section = PageSection(
                id=uuid4(),
                page_id=page.id,
                section_type=section_data["section_type"],
                order=section_data["order"],
                data=section_data["data"],
            )
            db.add(section)

        return created
    
    try:
        # Get admin user ID (first admin user in system)
        from app.models.user import User, UserRole
        admin_user = db.query(User).filter(User.role == UserRole.admin.value).first()
        
        if not admin_user:
            print("❌ Error: No admin user found in database")
            print("   Create an admin user first via the application signup/admin creation")
            return
        
        admin_id = admin_user.id
        print(f"✓ Using admin user: {admin_user.username or admin_user.email}")
        
        # Reset existing CMS pages before reseeding so the content always matches the current defaults.
        existing_count = db.query(Page).count()
        if existing_count > 0:
            existing_section_count = db.query(PageSection).count()
            print(f"⚠ CMS already contains {existing_count} pages and {existing_section_count} sections. Resetting and reseeding.")
            db.query(PageSection).delete(synchronize_session=False)
            db.query(Page).delete(synchronize_session=False)
            db.flush()

        seeded = 0

        # Seed all pages
        for slug, languages in PAGES_DATA.items():
            for lang, page_data in languages.items():
                upsert_page(slug, lang, page_data, admin_id)

                seeded += 1
                print(f"✓ Seeded {slug} ({lang})")

        db.commit()
        if existing_count > 0:
            print(f"\n✅ CMS reset complete; reseeded {seeded} pages")
        else:
            print(f"\n✅ Successfully seeded {seeded} pages into CMS")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
