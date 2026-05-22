#!/usr/bin/env python3
"""
run_final_report.py - Populates and generates the final governance report.
"""

from pathlib import Path
from evidence.final_report_generator import FinalReportGenerator

def main():
    cases = [
        {
            "case_id": "CASE_002",
            "topic": "Jobs Creation",
            "divergence_type": "Promise vs Outcome",
            "promise_text": "The UDC manifesto and campaign material promised to create at least 450,000 to 500,000 jobs within five years and to deliver 100,000 jobs within the first 12 months. This commitment was framed as part of the theme 'Decent Jobs, Decent Lives' and was intended to transform Botswana’s economy by pursuing an annual growth rate above 10 %.",
            "promise_video_title": "Duma Boko, Botswana's President Elect, Promises to 500 000 New Jobs in 5 Years – ‘I Dare Not Fail!’",
            "promise_video_url": "https://www.youtube.com/watch?v=e0MLzB5nGDc",
            "promise_timestamp": "01:15",
            "outcome_text": "By early 2025, the promised job boom had not materialised. The unemployment rate remained high (27.6 % in Q1 2024) according to Statistics Botswana. Independent monitors found that the UDC government planned to create only around 2,300 jobs (2,000 via the Khoemacau copper mine and 300 via the Menzi Battery Metals Project), far below the 450–500 k targets.",
            "analysis_text": "The divergence between the ambitious job-creation promise and actual outcomes is substantial. The manifesto’s numeric targets created concrete expectations, yet early actions did not match these commitments. Economic constraints, including a downturn in diamond revenues, were cited as reasons for slow job creation, but these explanations were not part of the original promise.",
        },
        {
            "case_id": "CASE_006",
            "topic": "Healthcare Reform",
            "divergence_type": "Promise vs Outcome",
            "promise_text": "During the 2024 campaign, President Duma Boko pledged to introduce a National Health Insurance scheme for all citizens and to invest in digital health technologies to modernise healthcare. He argued that universal health coverage and digital health would ensure timely and equitable healthcare for Batswana.",
            "promise_video_title": "Exclusive – Botswana's Duma Boko talks Economy, Corruption & Foreign Policy",
            "promise_video_url": "https://www.youtube.com/watch?v=NcF35I0GiTM",
            "promise_timestamp": "12:45",
            "outcome_text": "In August 2025, President Boko declared a state of public health emergency after the national medical supply chain collapsed. Clinics ran out of medicines; patients went without treatment and prices were inflated. Boko blamed the failure of the Central Medical Stores and budget constraints caused by a downturn in diamond revenues and reduced donor funding.",
            "outcome_video_title": "Botswana Declares Health Emergency: Boko Secures 36 Tonnes of Medicines",
            "outcome_video_url": "https://www.youtube.com/watch?v=ZsxLObyHUYE",
            "outcome_timestamp": "00:45",
            "analysis_text": "This case shows a strong divergence between promise and outcome. The pledge to modernise healthcare and roll out universal health insurance was followed by a collapse in the medical supply chain and declaration of a health emergency. External shocks such as the diamond revenue downturn contributed, but the crisis highlights systemic weaknesses not addressed by the promised reforms.",
        },
        {
            "case_id": "CASE_001",
            "topic": "Manifesto Contract",
            "divergence_type": "Obligation Denial",
            "promise_text": "The UDC manifesto was framed as a 'pledge and commitment' to the people of Botswana and a framework of accountability. Duma Boko encouraged citizens to hold his party to the manifesto, describing it as the basis for trust and responsibility.",
            "outcome_text": "After taking office, President Boko reportedly told a public meeting that 'a promise to voters is not a legal contract'. While widely shared on social media, no reputable news outlet reported this statement. However, the sentiment indicates a shift from viewing the manifesto as a binding contract to treating promises as aspirational.",
            "analysis_text": "The shift from describing the manifesto as an accountability framework to suggesting that political promises are not legally binding constitutes an obligation-denial divergence. Evidence is weaker here because the controversial statement is not corroborated by mainstream media. However, economic constraints cited after taking office illustrate a broader tendency to downplay earlier commitments.",
        },
        {
            "case_id": "CASE_004",
            "topic": "Economic Diversification",
            "divergence_type": "Economic Constraint Justification",
            "promise_text": "During the 2024 campaign, Boko pledged to diversify Botswana’s economy and achieve sustainable growth exceeding 10 % of GDP per annum. He highlighted plans to invest in manufacturing, particularly clothing, textiles, leather and footwear.",
            "promise_video_title": "Exclusive – Botswana's Duma Boko talks Economy, Corruption & Foreign Policy",
            "promise_video_url": "https://www.youtube.com/watch?v=NcF35I0GiTM",
            "promise_timestamp": "05:20",
            "outcome_text": "After taking office, the UDC government cited sluggish diamond sales and record-low government reserves as major challenges. The 2025/26 budget speech proposed creating only a few thousand jobs and modest tax increases, deviating from the ambitious growth and diversification plans.",
            "analysis_text": "This case demonstrates how external economic pressures were used to justify scaling back bold diversification promises. While the original manifesto set precise growth and diversification targets, later pronouncements acknowledged fiscal realities and proposed far more limited measures.",
        },
        {
            "case_id": "CASE_003",
            "topic": "Anti-Corruption",
            "divergence_type": "Governance Distancing",
            "promise_text": "The UDC manifesto pledged to 'fight corruption and create accountable government', acknowledging that corruption, nepotism and patronage were endemic in the public sector. Duma Boko promised to strengthen institutions and emphasised zero tolerance for graft.",
            "promise_video_title": "President Boko’s Bold Stand Against Corruption: International Anti-Corruption Day",
            "promise_video_url": "https://www.youtube.com/watch?v=R90F8eS0P1s",
            "promise_timestamp": "02:10",
            "outcome_text": "Despite the pledge, citizen protests erupted within months of taking office, with allegations of corruption at the Citizen Entrepreneurial Development Agency (CEDA) and other state entities. A forensic audit and investigations were launched, but official reports remained secret.",
            "analysis_text": "The anti-corruption case illustrates a gap between rhetoric and action. While Boko pledged robust institutions and fair trials, early evidence suggests persistent corruption concerns and slow progress on reforms. transparency was limited and protesters remained unsatisfied.",
        }
    ]

    generator = FinalReportGenerator(Path("outputs/reports"))
    report_path = generator.generate(cases, "DUMA_BOKO_FINAL_FORENSIC_REPORT.docx")
    print(f"Final Forensic Report Generated: {report_path}")

if __name__ == "__main__":
    main()
