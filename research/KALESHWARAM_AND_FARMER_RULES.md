# Kaleshwaram and farmer support evidence

Reviewed on 24 October 2026. Historical design context must not be presented as present safe operating capacity.

## Kaleshwaram

[CAG Chapter III](https://cag.gov.in/webroot/uploads/download_audit_report/2024/06_Chapter-III_Re-Engineering-of-PCSS-Project-065cdab56237fe3.51374325.pdf) describes reverse pumping from Medigadda through Annaram and Sundilla toward Yellampally. Its construction-context storage figures are 16.17, 10.87 and 8.83 TMC respectively. These are not live readings or additive new basin yield. The [2024 executive summary](https://saiindia.gov.in/uploads/download_audit_report/2024/03_Executive-Summary-065cdab561be1e6.64616893.pdf) records the original 2 TMC/day design and a later 3 TMC/day expansion; neither establishes current operating availability.

[BHEL's commissioning release](https://tenders.bhel.com/sites/default/files/5dd236dc546ecBHEL_commissions_14_Pumping_Units_of_Kaleshwaram_Lift_Irrigation_Scheme_in_Telangana_in_a_record_period_of_six_months.pdf) identifies Package 6 as Yellampally to Medaram, with seven 116 MW units; Package 8 has seven 139 MW units and lifts from Package 7 discharge toward Mid Manair. It describes per-pump flow of 89 m³/s against a head of 100–125 m. The app derives installed package power by multiplying unit count and unit rating, then calculates a user-assumption envelope capped by hydraulic flow, available power and hours.

The [Telangana restoration statement from July 2026](https://www.telangana.gov.in/news/2026/07/honble-cm-sri-a-revanth-reddy-participated-in-presentation-on-irrigation-projects-at-jyotirao-phule-praja-bhavan-hyd/) discusses technical restoration concerns. JalaSetu therefore shows current safe capacity as unverified and offers no gate/pump operation. Tank and farm branches in the animation are illustrative connections, not verified project topology.

## Farmer water rules

[FAO irrigation needs](https://www.fao.org/4/s2022e/s2022e08.htm) explains that effective rain offsets irrigation demand and that paddy needs additional consideration of land preparation, seepage and water-layer requirements. The calculator uses locally supplied supplemental-application depths and allowances; it does not apply monthly effective-rain equations to a daily forecast or estimate a full season.

[ICAR IIRR](https://icar-iirr.org/index.php/en/component/content/article/33-iirr-technologies/113-technology-10?Itemid=258) provides alternate wetting and drying context for rice. The app suggests local agronomic review rather than a universal drying schedule or savings guarantee. Flowering and reported critical stress block generic forecast-only deferral.

[Open-Meteo documentation](https://open-meteo.com/en/docs) documents daily rain, precipitation probability and reference evapotranspiration. Its daily probabilities do not give the probability of receiving an entire multi-day rainfall total. Forecast previews load into forecast fields only; verified effective rain is a separate observation.

## Event and notification rules

Excess release is evaluated against configured demo rate/volume thresholds, with a configurable tolerance. These thresholds require signed-order linkage and calibrated meters in production. In-app power windows describe a utility schedule separately from current feeder observation; they never guarantee uninterrupted future supply. Unknown or expired observations must not be described as power available.

No public feeder-status API, validated real farm sensor feed, external SMS delivery or authoritative live operating clearance has been verified in this prototype. The provided event-ingest interfaces and in-app alert workflow are demonstrations of the control flow needed for those integrations.
