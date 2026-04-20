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
- Age: 54
- Height/weight: 5'10", 184 lbs
- Location: Guthrie, OK

Current prescription therapies:
- Testosterone Cypionate 35 mg twice weekly subcutaneous (70 mg/week total, split dosing to flatten peaks), prescribed by Dr. Brian Lamkin

Current supplement stack (with start dates — critical for interpreting lab trends):
- Vitamin D3 10,000 IU daily — started approximately 2018 (longstanding)
- DIM (DIMPRO 100) 100 mg daily — started approximately 2022 (longstanding)
- PerQue Life Guard multivitamin/multimineral, 2 tabsules daily — started approximately 2020 (longstanding)
- Fish Oil (Nature Made 1200mg, ~720 mg combined EPA+DHA) — discontinued April 20, 2026
- Fish Oil (Nordic Naturals Ultimate Omega 2X, 2 softgels nightly, 2160 mg combined EPA+DHA) — STARTED April 20, 2026 (today; has not yet affected any existing lab values)
- TMG (Betaine) NOW Foods 1000 mg, 1 tablet breakfast + 1 tablet dinner (2000 mg daily total) — STARTED April 20, 2026 (today; has not yet affected any existing lab values)
- Vitamin K (Life Extension Super K, 1 softgel daily with dinner) — STARTED April 20, 2026 (today; has not yet affected any existing lab values)
- 5-HTP 200 mg (Arazo Nutrition) — DISCONTINUED April 20, 2026 (previously longstanding)

Most recent blood draw: January 27, 2026. Values from this draw cannot have been influenced by supplements initiated after this date.

Next scheduled blood draw: July 2026 (post-visit with Dr. Lamkin in August 2026). This will be the first draw reflecting the new supplement stack started April 20, 2026.

Current blood donation pattern:
- Donates at the Oklahoma Blood Institute
- Historical pattern: irregular (last donation July 2025 before the Jan 27 2026 lab draw - approximately 6 months between donation and draw)
- Current pattern: committed to every 6 weeks going forward (most recent donation April 2026)
- Clinical relevance: Jan 2026 hematocrit 52.6% was measured at peak red cell mass between donations; current hematocrit is likely materially lower. Going forward, regular donations should keep hematocrit in a safer range and also help manage ferritin given HFE H63D carrier status.

Current eating pattern and lifestyle:
- Intermittent fasting: eating window roughly 11am to 7pm daily (16:8 pattern)
- Morning: 2 cups caffeinated coffee, then decaf until eating window opens (appetite suppression)
- Extended fasting: completed two 65-hour water fasts in 2026 (January and Easter); considering quarterly cadence
- No added sugar since January 2026
- Low-carb eating pattern generally; avoids bread
- Typical foods: eggs (boiled, fried, poached), red meat, chicken, fish, cheddar cheese, pork rinds with sour cream/zesty ranch/chipotle-in-adobo dip (regular snack), peanuts, prunes, sauerkraut, pickled jalapeños, pickled okra
- Training: 3-stripe brown belt Brazilian jiu-jitsu; private lesson with black belt instructor every Sunday morning; monthly no-gi open mat sessions with training partners followed by breakfast
- Loaded carry/rucking: walk-behind mowing of large acreage (60-inch deck) with 45-pound weighted vest; typically Fridays and weekends due to weekday work schedule
- Work pattern: works from home, sedentary at computer most of the workday

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
