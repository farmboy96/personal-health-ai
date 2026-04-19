"""
Static user context injected into AI health prompts.
This lets the interpreter produce targeted analysis instead of hedging
across possibilities it could infer from the data anyway.

Edit freely as circumstances change. Avoid putting anything here you
would not want sent to the OpenAI API.
"""

USER_CONTEXT = """
Subject profile:
- Sex: male
- Age: [FILL IN]
- Height/weight: [FILL IN or leave blank]
- Location: Phoenix, AZ

Current prescription therapies:
- Testosterone Cypionate 80 mg/week subcutaneous (0.4 mL of 200 mg/mL), prescribed by Dr. Brian Lamkin

Current supplement stack (all taken at night):
- Vitamin D3 10,000 IU daily
- DIM (DIMPRO 100) 100 mg daily — estrogen metabolism modulator
- 5-HTP 200 mg daily (2 capsules Arazo Nutrition) — serotonin precursor
- Fish Oil 2400 mg daily (720 mg combined EPA+DHA from 2x Nature Made 1200mg softgels)
- PerQue Life Guard multivitamin/multimineral, 2 tabsules daily

Known genetic predispositions (from Promethease/SNPedia analysis of AncestryDNA raw data, April 2026):
- MTHFR A1298C homozygous variant (rs1801131 C/C); MTHFR C677T normal (rs1801133 C/C) — partial reduction in folate-to-methylfolate conversion; bears on homocysteine metabolism
- HFE H63D heterozygous carrier (rs1799945 C/G); HFE C282Y normal (rs1800562 G/G) — mild iron-retention tendency; avoid iron supplementation without deficiency evidence
- APOA2 rs5082 C/C — saturated fat has stronger obesity/metabolic impact; Mediterranean-pattern diet preferred over high-saturated-fat
- LPL rs326 A/A — genetic tendency toward lower HDL cholesterol
- CETP rs1864163 A/G — one copy of higher-HDL variant (partial offset)
- FOXO3 rs2802292 G/G and rs2802288 A/A — longevity-associated variants
- KLOTHO KL-VS heterozygous (rs9536314 G/T) — longevity/cognition-associated
- Elevated prostate-cancer polygenic profile (multiple risk variants across FGFR4, MSMB, HNF1B) — maintain PSA surveillance
- CYP2R1 rs2060793 A/A — genetic tendency toward lower serum vitamin D (justifies higher D3 dose)
- MAOA rs6323 T/T — reduced MAOA activity (slower clearance of serotonin/dopamine/norepinephrine)
- rs17713054 A/G — elevated COVID severity risk
- TG rs180223 G/T — elevated autoimmune thyroid disease risk; monitor TSH trends carefully
- rs9268839 G/G — elevated rheumatoid arthritis risk; flag any unexplained joint symptoms

Relevant conditions/history: [FILL IN if any]
Lifestyle notes: [FILL IN — training, sleep pattern, alcohol, stress level]
""".strip()
