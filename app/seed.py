"""All volumes, routes, villages and operating inputs below are invented demo fixtures."""
from datetime import datetime, timezone
from .models import Dataset


def seed():
    now = datetime.now(timezone.utc).isoformat()
    specs = [
        ('srisailam', 'Srisailam', 'Krishna', 215.8, 57.29, 53.85, 5, 16.08, 78.90),
        ('sagar', 'Nagarjuna Sagar', 'Krishna', 312, 165, 130, 18, 16.58, 79.31),
        ('jurala', 'Jurala', 'Krishna', 9.66, 6, 2, 1, 16.33, 77.71),
        ('sriramsagar', 'Sri Ram Sagar', 'Godavari', 80.5, 43, 12, 7, 18.97, 78.34),
        ('yellampally', 'Sripada Yellampally', 'Godavari', 20.18, 14, 4, 3, 18.83, 79.38),
        ('singur', 'Singur', 'Manjira', 29.92, 8, 4, 5, 17.75, 77.93),
        ('mallanna', 'Mallanna Sagar', 'Godavari', 50, 17, 4, 4, 18.07, 78.77),
        ('lower-manair', 'Lower Manair', 'Godavari', 24.07, 12, 3, 3, 18.41, 79.12),
    ]
    reservoirs = [dict(id=i, name=n, basin=b, capacity_tmc=c, storage_tmc=s,
        operating_floor_tmc=f, drinking_reserve_tmc=d, other_commitments_tmc=.3,
        environmental_reserve_tmc=.2, hydro_hold_tmc=.5, observed_at=now,
        source='Synthetic demonstration fixture — not a current government reading',
        latitude=lat, longitude=lon) for i,n,b,c,s,f,d,lat,lon in specs]
    villages=[]
    districts=['Nagarkurnool', 'Nalgonda', 'Jogulamba Gadwal', 'Nizamabad', 'Mancherial', 'Sangareddy', 'Siddipet', 'Karimnagar']
    for idx,r in enumerate(reservoirs):
        for j in range(2):
            villages.append(dict(id=f'V{idx+1:02}{j+1}', name=f'{districts[idx]} demo village {j+1}',
                district=districts[idx], reservoir_id=r['id'], crop='Paddy' if j==0 else 'Maize',
                stage='flowering' if j==0 else 'new planting', area_ha=1800+idx*150+j*200,
                population=2400+idx*250, net_irrigation_mm=55 if j==0 else 30,
                soil_credit_mm=5, efficiency=.6, lift_head_m=65 if idx in [0,4,6] else 0,
                pump_efficiency=.75, pump_capacity_mw=1.2, power_hours_day=8,
                canal_capacity_cusecs=95, travel_hours=18, deadline_days=5 if j==0 else 10,
                tail_end=j==1))
    return Dataset(label='Telangana planning sandbox • 8 reservoirs / 16 fictional villages',
                   mode='synthetic_demo', reservoirs=reservoirs, villages=villages).model_dump(mode='json')
