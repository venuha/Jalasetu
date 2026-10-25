"""Sourced design context, separated from unknown operating availability."""
from .models import StrictModel
from pydantic import Field

CAG='https://cag.gov.in/webroot/uploads/download_audit_report/2024/06_Chapter-III_Re-Engineering-of-PCSS-Project-065cdab56237fe3.51374325.pdf'
BHEL='https://tenders.bhel.com/sites/default/files/5dd236dc546ecBHEL_commissions_14_Pumping_Units_of_Kaleshwaram_Lift_Irrigation_Scheme_in_Telangana_in_a_record_period_of_six_months.pdf'
STATE='https://www.telangana.gov.in/news/2026/07/honble-cm-sri-a-revanth-reddy-participated-in-presentation-on-irrigation-projects-at-jyotirao-phule-praja-bhavan-hyd/'
TMC=28_316_846.592

class LiftScenario(StrictModel):
    package: str = Field(default='6',pattern='^(6|8)$')
    online_units: int = Field(default=7,ge=0,le=7)
    hours_day: float = Field(default=12,ge=0,le=24)
    head_m: float = Field(default=110,gt=0,le=1000)
    efficiency: float = Field(default=.85,gt=0,le=1)
    available_power_mw: float = Field(default=600,ge=0,le=2000)
    requested_tmc_day: float = Field(default=.8,ge=0,le=10)
    delivery_efficiency: float = Field(default=.9,gt=0,le=1)


def lift_capacity(sc:LiftScenario):
    unit_mw=116 if sc.package=='6' else 139
    installed=sc.online_units*unit_mw
    available=min(installed,sc.available_power_mw)
    hydraulic_q=sc.online_units*89
    power_q=available*1e6*sc.efficiency/(1000*9.81*sc.head_m)
    actual_q=min(hydraulic_q,power_q)
    volume=actual_q*sc.hours_day*3600
    energy=1000*9.81*volume*sc.head_m/sc.efficiency/3.6e9
    possible=volume/TMC
    req=sc.requested_tmc_day
    req_energy=1000*9.81*req*TMC*sc.head_m/sc.efficiency/3.6e9
    return dict(mode='design_based_hypothetical',current_safe_operating_capacity=None,
        status='Engineering and operating clearance unverified; not an executable dispatch',
        package=sc.package,installed_mw=installed,usable_power_mw=available,
        hydraulic_ceiling_cumecs=hydraulic_q,power_ceiling_cumecs=power_q,
        feasible_flow_cumecs=actual_q,lifted_tmc_day=possible,delivered_tmc_day=possible*sc.delivery_efficiency,
        energy_mwh=energy,requested_energy_mwh=req_energy,
        requested_coverage_pct=min(100,possible/req*100) if req else 100,
        bottleneck='No operating hours' if sc.hours_day==0 else 'Power / head' if power_q<hydraulic_q else 'Pump flow design',
        assumptions=sc.model_dump(),source=BHEL,
        note='Single-package steady-state envelope. This is not whole-project or current operating capacity; it excludes intermediate storage, pump curves, cavitation, ramping and network constraints.')


def network():
    return dict(name='Kaleshwaram lift irrigation',mode='sourced_design_context',operational_status='Unverified',
        baseline_design_tmc_day=2,baseline_design_cumecs=2*TMC/86400,
        nodes=[
            dict(id='medigadda',name='Medigadda',kind='barrage',capacity_tmc=16.17,x=90,y=310,source=CAG),
            dict(id='annaram',name='Annaram',kind='barrage',capacity_tmc=10.87,x=270,y=250,source=CAG),
            dict(id='sundilla',name='Sundilla',kind='barrage',capacity_tmc=8.83,x=450,y=190,source=CAG),
            dict(id='yellampally',name='Yellampally',kind='reservoir',capacity_tmc=None,x=650,y=145,source=CAG),
            dict(id='medaram',name='Medaram',kind='reservoir',capacity_tmc=None,x=850,y=100,source=BHEL),
            dict(id='tank',name='Village tank',kind='illustrative',capacity_tmc=None,x=850,y=335,source=None),
            dict(id='farms',name='Farm outlets',kind='illustrative',capacity_tmc=None,x=650,y=380,source=None)],
        edges=[
            dict(source='medigadda',target='annaram',kind='lift',label='Reverse lift'),
            dict(source='annaram',target='sundilla',kind='lift',label='Reverse lift'),
            dict(source='sundilla',target='yellampally',kind='lift',label='Reverse lift'),
            dict(source='yellampally',target='medaram',kind='lift',label='Package 6'),
            dict(source='medaram',target='tank',kind='illustrative',label='Illustrative distribution'),
            dict(source='tank',target='farms',kind='gravity',label='Illustrative gravity outlet')],
        packages=[dict(id='6',name='Package 6',route='Yellampally → Medaram',units=7,unit_mw=116,unit_cumecs=89),
                  dict(id='8',name='Package 8',route='Package 7 discharge → Mid Manair',units=7,unit_mw=139,unit_cumecs=89)],
        sources=[dict(title='CAG 2024 design and barrage context',url=CAG),dict(title='BHEL pump design and package routes',url=BHEL),dict(title='Telangana July 2026 restoration statement',url=STATE)],
        caution='Capacity figures describe historical design/construction context, not current storage or permission to operate. Village tank and farm links are illustrative; the schematic omits intermediate works and is not a geographic map. Do not sum serial barrage capacities as new water yield.')
