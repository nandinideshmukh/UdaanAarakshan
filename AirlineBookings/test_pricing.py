import asyncio
import sys
sys.path.append('E:/AirlineBookings/backend')
from app.services.aviationstack_client import _estimate_prices_via_llm, _formula_price

flights = [
    {'flight_number': '6E123', 'airline': 'IndiGo', 'duration_minutes': 130, 'departure_time': '08:00'},
    {'flight_number': 'AI456', 'airline': 'Air India', 'duration_minutes': 130, 'departure_time': '08:30'}
]

async def main():
    print('--- _formula_price ---')
    for f in flights:
        print(f"{f['airline']}: {_formula_price(f['flight_number'], f['duration_minutes'], 'economy')}")
    print('\n--- _estimate_prices_via_llm ---')
    try:
        llm_prices = await _estimate_prices_via_llm(flights, 'Delhi', 'Mumbai', 'economy')
        for f in flights:
            print(f"{f['airline']}: {llm_prices.get(f['flight_number'])}")
    except Exception as e:
        print('Error:', e)

asyncio.run(main())