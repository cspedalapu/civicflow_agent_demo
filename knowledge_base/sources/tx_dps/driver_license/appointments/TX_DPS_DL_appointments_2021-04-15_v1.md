# Texas DPS — Driver License Services: Appointments (Policy + Demo Handling)

Source: https://www.dps.texas.gov/section/driver-license/driver-license-services-appointments  
Publisher: Texas Department of Public Safety (DPS)  
Page date: 2021-04-15  
Captured type: URL (web page)  
Retrieved at: 2026-01-22  

---

## 1) Official Appointment Policy (Authoritative Summary)

- All in-office driver license (DL) and identification (ID) card services are by appointment only.
- DPS encourages eligible customers to complete services online (see DL Services, Extensions, and Waivers / Online Services).
- A limited number of additional appointments may be released daily at most driver license offices; these are released throughout the day and can be scheduled online.
- Building entry policy: only customers are allowed into the building, with exceptions (ADA accommodations, customers with small children, elderly persons, and certain business needs such as parental authorization or residency/address change scenarios).
- Payment guidance: credit cards are preferred; money orders, cashier’s checks, and personal checks are accepted for the correct amount.
- If requirements are not met, customers may be required to reschedule.

---

## 2) Official Links (Must Share When Requested)

If a customer requests an appointment link (or says “schedule/book appointment”), the assistant must share BOTH:

1) Appointment information page (rules + FAQs):
- https://www.dps.texas.gov/section/driver-license/driver-license-services-appointments

2) Appointment scheduler (booking site):
- https://www.txdpsscheduler.com/

Recommended wording:
“Texas DPS requires appointments for in-office driver license and ID services. Here are the official links:
- Appointment information (rules + FAQs): https://www.dps.texas.gov/section/driver-license/driver-license-services-appointments
- Appointment scheduler: https://www.txdpsscheduler.com/”

---

## 3) FAQs and Operational Answers (From DPS Page)

1) How do I schedule an appointment?
- Use the appointment scheduler: https://www.txdpsscheduler.com/

2) If I don’t have an appointment, can I still go into an office and be served?
- Without an appointment, customers may use a self-service kiosk inside the office to schedule (if available), or schedule for another day/location.

3) My local office is not listed in the scheduler—why?
- If an office is not listed, there are currently no available appointments. Select the next closest office.

4) Are same-day appointments possible?
- Most DL offices have a limited number of same-day appointments, and these fill quickly.

5) What kinds of appointments can I schedule?
- DL and ID services can be scheduled; the scheduler may also indicate whether you are eligible to complete the service online via Texas.gov without visiting an office.

6) I am moving to Texas—do I need an established Texas DL/ID to schedule?
- No. The scheduler asks questions to determine whether you previously established a DL/ID in Texas; it allows appointments for new and existing customers.

7) Can I schedule an appointment for another person?
- Yes, if you have the required information; DPS notes this is not recommended.

8) What if there are no appointments available at my local office?
- Schedule at another location or check back later for cancellations. Same-day appointments may be available online on a limited basis.

9) What if I can’t schedule before my DL/ID expires?
- Check eligibility to renew online at Texas.gov. If not eligible, schedule as soon as possible. Texas allows renewal up to two years before the expiration date.

10) What if I don’t see the service I need?
- Choose “Service Not Listed” to schedule. Note: Texas guidance indicates you generally may not hold both a DL and an ID simultaneously; if you already have one, you may not be offered the option for the other. Use “Service Not Listed” and be prepared to surrender the existing DL or ID if required.

11) How far in advance can I schedule?
- Up to six months in advance.

12) How late can I be before my appointment is cancelled?
- Appointments are cancelled after 30 minutes.

13) How early should I arrive?
- Arrive no earlier than 30 minutes prior to your appointment.

14) How do I change/reschedule my appointment?
- Use the appointment scheduler to reschedule. Once a new appointment is confirmed, the existing appointment is automatically cancelled.

15) How do I confirm my appointment?
- Confirmation details are provided when booked and can be obtained by logging back in to the scheduler.

16) Will I receive notifications?
- Optional email or text notifications are available; a valid email is recommended for receiving pertinent information.

17) If I cancel, how long must I wait to reschedule?
- You may reschedule immediately after cancelling.

---

## 4) Demo Behavior Specification (For Call Center AI)

### 4.1 Intent: “Share appointment link”
When user intent is “share link / scheduler link / appointment link”:
- Provide both official links in Section 2.
- Provide a one-line appointment-only policy reminder.

### 4.2 Intent: “Book an appointment”
For the demo, DO NOT claim that the appointment was booked on the DPS website.
Instead:
1) Collect information (see Section 4.3)
2) Create a “Demo Appointment” in Google Calendar (future implementation)
3) Provide the user the two official links (Section 2) and advise they must finalize booking on the scheduler if required.

Suggested disclaimer:
“For the demo, I can capture your details and create a calendar hold. You will still need to finalize the appointment on the official DPS scheduler.”

### 4.3 Data to collect for booking (MVP)
- Service type (renew / replace lost / apply new DL or ID / change address or name / CDL / other)
- Preferred location (city or office name)
- Preferred date range (e.g., this week / next week / specific date)
- Preferred time window (morning/afternoon or specific time)
- Customer name (for calendar title)
- Contact method (phone or email for confirmation in demo)
- Notes/constraints (urgency, language preference, ADA needs, bringing child/elderly person, etc.)

### 4.4 Calendar event template (for later implementation)
- Title: “DPS Appointment (Demo) — <Service Type> — <Customer Name>”
- Location: “<Office/City> (Texas DPS)”
- Description includes:
  - Captured service request details
  - Both official links (info page + scheduler)
  - Reminder: “This is a demo calendar hold; user must finalize on https://www.txdpsscheduler.com/”

---

## 5) Source Reference
Official appointment policy, scheduling rules, and FAQs are based on:
https://www.dps.texas.gov/section/driver-license/driver-license-services-appointments
