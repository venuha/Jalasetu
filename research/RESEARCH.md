# Telangana water availability and AI feasibility

Assessment date: 24 October 2026. Web observations can change; retain each underlying observation date rather than treating the retrieval date as its measurement date.

## What the evidence supports

Water stress deserves investigation at irrigation-command and village level. A statewide claim that all farming has been prohibited is not established by the sources below. Likewise, Srisailam is important to the Krishna system but cannot represent all of Telangana, including Godavari-dependent farms.

| Evidence | Finding | Interpretation |
| --- | --- | --- |
| [Telangana IDSS](https://idss.telangana.gov.in/telangana/), indexed update 22 October 2026 | Rainfall 596.86 mm versus normal 845.71 mm, deviation −29.42%; 87 reservoirs collectively at 470.55 of 1,059.3 TMC | Official portal discovery, but its dynamically rendered body was not readable through the web fetch. Confirm rainfall accumulation period and scope before operational use. Aggregate storage does not establish local access. |
| [Deccan Chronicle](https://www.deccanchronicle.com/southern-states/telangana/komatireddy-asks-farmers-to-shun-paddy-amid-water-shortage-1977674), 8 August 2026 | Indexed report says minister Komatireddy Venkata Reddy asked officials to discourage paddy in Nalgonda because of Nagarjuna Sagar shortages | Search excerpt only; full article returned 403. Obtain the actual agriculture advisory, districts, crop scope, season and validity. This is not evidence of a statewide ban on all crops. |
| [Telangana Today](https://telanganatoday.com/water-shortage-leaves-siddipet-paddy-farmers-at-crossroads), 16 July 2026 | Reports delayed sowing, groundwater stress and protests over unscheduled power cuts in Siddipet; describes dependence on Godavari lifts | Local reporting supports investigating water delivery and feeder reliability together. Government-failure allegations remain the publication's claims. July conditions cannot establish October feeder conditions. |
| [NOAA CPC ENSO discussion](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml), issued 8 October 2026 | El Niño Advisory, with strong to very strong conditions likely through January–March 2027 | A seasonal risk signal, not a quantitative forecast of rain over a particular Telangana farm or Krishna inflow. |

A formal drought declaration, its mandal list, and the current crop restriction order have not been established from a primary government order here. Retrieve them before representing either as an official current statewide policy.

## How much water is in Srisailam

The [AP Reservoirs dashboard](https://ap-reservoirs.vercel.app/reservoirs/srisailam-r), an independent website attributing data to APWRIMS, displays this observation for **24 October 2026**:

| Metric | Reported value |
| --- | --- |
| Storage | 57.29 TMC |
| Storage percentage | 26.5% |
| Water level | 836.80 ft |
| Inflow | 0 cusecs |
| Outflow | 3,854 cusecs |

These are provisional secondary figures. [APWRIMS](https://apwrims.ap.gov.in/) returned a JavaScript shell, and a same-day primary bulletin was not obtained. The [KRMB homepage](https://krmb.gov.in/krmb/home) search index instead exposed an older Srisailam reading dated 30 June 2026, which cannot verify October storage.

The [KRMB project specification](https://www.krmb.gov.in/html/project19.html) lists gross capacity 215.807 TMC, irrigation minimum drawdown level 854 ft with corresponding storage 89.29 TMC, and power minimum drawdown level 834 ft with corresponding storage 53.851 TMC. These are published project specifications, not a substitute for current operating orders or an updated elevation–storage curve.

The secondary reading is below the listed irrigation drawdown level. Subtracting the published power threshold gives 57.29 − 53.851 = **3.439 TMC above that reference threshold**. This is only an illustrative comparison of two sources. It is not an irrigation allocation: outlet-specific access, drinking-water commitments, allocations, current orders, sedimentation and pumping constraints still matter. The independent dashboard's dead-storage value also differs from KRMB's specification, reinforcing the need to reconcile definitions.

One TMC is 28.316846592 million cubic metres. The reported gross storage is therefore about **1,622.3 million m³**. At a constant 3,854 cusecs, outflow would be 0.3329856 TMC/day. Dividing all gross storage by that rate would misleadingly count operationally inaccessible and reserved water. Do not present it as days of irrigation remaining.

## APIs and data access

“Documented” below means that provider documentation was accessible. It does not mean an authenticated production integration, uptime, freshness, quotas or data coverage has been tested.

| Source | Interface and useful fields | Access status and next action |
| --- | --- | --- |
| [IMD API reference](https://api.imd.gov.in/public/api_reference.html) and [access portal](https://api.imd.gov.in/public/index.php) | Published weather observations, city forecasts, district rainfall forecasts, warnings and subdivision rainfall forecasts. Example documented path: `https://api.imd.gov.in/api/v1/subdivision_rainfall_forecast` | Documented official interface. Portal offers registration. Confirm product-specific authentication, terms and station coverage with a real request. Do not interpret rainfall distribution categories as a catchment rainfall volume. |
| [Open-Meteo](https://open-meteo.com/en/docs) | Forecast API: `https://api.open-meteo.com/v1/forecast`; precipitation, temperature, and `et0_fao_evapotranspiration` | Documented supplementary weather interface. Verify current licensing and commercial plan before deployment. ET₀ is reference evapotranspiration, not a direct crop-water requirement. Model soil moisture is not a farm sensor. |
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/) | Documented meteorological and solar data API; supports weather-baseline work | Supplement historical context; validate spatial resolution, latency and parameter units for the chosen location. It does not measure reservoir storage or canal releases. |
| [Copernicus Data Space APIs](https://documentation.dataspace.copernicus.eu/APIs.html) | Sentinel imagery through STAC, OData and processing services. Documented catalogue: `https://catalogue.dataspace.copernicus.eu/odata/v1/Products` | Useful for changes in cropped area, vegetation and surface-water extent. Verify authentication and service quotas for imagery downloads and processing. Ground-truth classifications. Satellite surface area alone cannot establish TMC without bathymetry. |
| [Telangana IDSS](https://idss.telangana.gov.in/telangana/) | Reservoirs, rainfall, tanks, groundwater and river gauges in a government dashboard | Portal discovered; no documented public API verified. Request an authorized export or data feed. Do not treat dashboard-internal calls as a supported public API. |
| [APWRIMS](https://apwrims.ap.gov.in/), [AP DES reservoir table](https://desweather.ap.gov.in/Realtime/ReservoirData.jsp), [KRMB](https://krmb.gov.in/krmb/home) | Reservoir levels, storage and potentially release components and operational bulletins | Government portals/reports; no documented public reservoir API verified here. AP DES's indexed reading was older. Obtain dated official daily bulletins or an authorized feed. |
| [National Water Data Portal](https://nwdp.nwic.gov.in/) and [India WRIS](https://nwic.in/wris/) | Surface water, groundwater and water-resource context | Official sources identified; portal fetch timed out. Availability of particular reservoir series, reuse terms and programmatic access remain unverified. Start with approved exports and request NWIC access. |
| [National Power Portal](https://npp.gov.in/publishedReports) | Published generation and hydro-reservoir reports, including PDF/XLS options | Suitable for daily context; no public feeder-level API verified. Obtain feeder outages, actual energized hours, voltage quality and lift-pump availability from the relevant DISCOM, TRANSCO and irrigation operator. State supply totals cannot establish a village outage. |

Crop calendars, sowing area, soil type, crop stage, pump head and efficiency, canal geometry and losses, outlet access, tail-end delivery, procurement and market access still require district agriculture staff, irrigation engineers, farmer organizations and field measurement. No verified single public API supplies all these inputs.

## A practical AI design

Begin with one distributary or small command area, tentatively in Nalgonda if the Nagarjuna Sagar crop advisory is the user's target. Trace its actual reservoir-to-field route before selecting the pilot. If the affected farms are in Siddipet, use their Godavari supply network instead.

1. **Evidence collection:** ingest dated reservoir bulletins, weather feeds, authorized canal schedules and local observations. AI extracts structured records from documents; arithmetic and schema checks verify them. Store observation time, retrieval time, source, units, measurement type and confidence. Flag stale readings and conflicting sources rather than averaging them blindly.
2. **Farm demand:** collect consented crop area, sowing date, stage, soil and water access. Estimate daily crop evapotranspiration using ETc = Kc × ET₀, effective rainfall and a soil-water balance. Paddy also needs separately modelled land preparation and seepage/percolation. Calibrate coefficients locally with an agronomist.
3. **Supply and power simulation:** model upstream inflows, reservoir levels, releases, diversions, evaporation, travel time, canal capacity, delivery efficiency, pump capacity and reliable power hours. Simulate dry, central and wet scenarios. The LLM explains model results; it does not invent measurements or optimize water allocations by free-form text.
4. **Decision comparison:** use an explicit constrained optimizer or rules engine to compare rescue irrigation, rotational delivery and voluntary alternative crop areas. Publish objectives such as avoiding drinking-water shortfalls, protecting crops at sensitive stages and improving tail-end access. Apply current allocation orders and outlet limits as constraints reviewed by the responsible agencies.
5. **Farmer service:** offer Telugu voice/text explanations of verified schedules, rainfall uncertainty and crop options. Distinguish an officially approved release from a proposed one. Farmers can report failed deliveries and outages; aggregate and cross-check reports before changing the model.
6. **Government evidence packet:** generate a reviewed request naming the villages, crop area and stage, delivery deadline, minimum release volume, power requirement, conveyance assumptions and alternatives. Show the consequences under low inflow and why the request preserves required reserves. Officials retain release authority.

Hydropower releases can continue downstream toward Nagarjuna Sagar, so count flows by route and time; do not subtract the same water twice as both power consumption and irrigation withdrawal. Lift irrigation consumes electricity and may fail even when reservoir water exists. Both relationships belong in the same model.

## An illustrative water request calculation

This example uses invented pilot inputs, not an assessment of current farmer requirements:

- Area: 10,000 hectares.
- Required net supplemental irrigation: 40 mm.
- Combined conveyance and application efficiency: 60%.

Net field demand = 10,000 × 40 × 10 = **4.0 million m³**. Source requirement = 4.0 / 0.60 = **6.667 million m³**, approximately **0.235 TMC**. Delivery over seven days requires a mean source flow of approximately **389 cusecs**, if the network can carry it throughout that period.

The conversion uses 1 mm over 1 hectare = 10 m³. Forty millimetres is a hypothetical supplemental application, not a full paddy-season requirement. A release request must use crop-stage and soil measurements, not copy this number.

For a lift with 50 m total dynamic head and 75% overall efficiency, pumping 6.667 million m³ would require approximately **1.21 GWh**, derived from E = ρgVH/η. Pumping only eight hours per day over seven days implies about **21.6 MW** average input while running and a corresponding higher pumping flow. Head, losses and efficiencies must be measured for each actual stage. These assumptions illustrate why a water-only request can fail.

## Pilot and conditions for proceeding

**First milestone:** obtain a same-day official reservoir bulletin, the actual crop advisory/order, the chosen command boundary and outlet route, and a week's canal and feeder records. Maintain a manually reviewed data ledger while access is negotiated. No automated release recommendation should depend on the uncorroborated secondary storage figure.

**Second milestone:** with an irrigation engineer, agronomist and farmer organization, reconstruct recent water delivery and compare estimated demand with measured flow and actual energized hours. Run the model in shadow mode and assess error in delivered water, timing and power use; compare with existing operational planning.

**Third milestone:** submit a reviewed scenario packet through an authorized local partner. Measure water reaching tail-end farms, crop survival, water per hectare and farmer cost against an agreed baseline. Report errors and uncertainty, not a promised yield improvement.

An initial pilot can use document extraction, public weather data, manual official uploads and deterministic calculations. Fine-tuning a language model is not a prerequisite. Stronger forecasts need several seasons of quality history and validation against simple baselines. Sensor installations and live government integration should follow the pilot's demonstrated data gaps.

The core benefit is a credible, quantified and locally deliverable request for water, paired with understandable farmer guidance. AI cannot create missing water, override allocation orders or guarantee government approval. Where a release is infeasible, the same evidence should support timely crop alternatives, loss documentation and assistance requests rather than an unsupported promise to farmers.
