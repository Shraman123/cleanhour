# LinkedIn post (draft — post it yourself)

A kWh used at noon in India emits 33% less CO₂ than one used at 9 pm.

I pulled 30 days of Grid-India's own data (30 Sep – 29 Oct 2026). Grid-India publishes all-India generation by fuel every 15 minutes, and I turned that into carbon intensity for every hour.

What the month showed:
☀️ 12:00 → 501 gCO₂/kWh (46% from solar, wind, hydro and nuclear)
🌙 21:00 → 747 gCO₂/kWh (18%)
💸 On the IEX day-ahead market, the same kWh cost ₹1.67 at noon and ₹9.00 at 9 pm

So I built CleanHour: a scheduler that runs heavy AI jobs (training, batch inference) in the cleanest window before their deadline.

`python -m cleanhour run --hours 2 --within 24 -- python train.py`

Does it work? I backtested it on every hour of the month. The scheduler could only see the past. Results for a 2-hour job:
→ 26.7% less CO₂ than starting immediately
→ perfect hindsight would have managed 27.0%
→ the price paid per kWh fell 76%

Then a real job. I trained a CNN on CIFAR-10 on my own laptop (GTX 1650, 13.7 min, 90.6% accuracy) and measured it with CodeCarbon: 17.6 Wh.
→ at noon: 8.8 g CO₂
→ at 9 pm: 13.1 g CO₂
That's tiny for one laptop. But shift 1 MWh of AI compute (about one 8-GPU server for 4 days) from 9 pm to noon and you avoid 246 kg of CO₂ and save ₹7,330 at exchange prices.

India's solar cycle is so regular that a simple "same hour last week" forecast gets almost all of the possible gain. Data centres and AI startups are mostly leaving this on the table.

Caveats: these are national averages and direct emissions only. Laptop GPU power is measured but CPU power is estimated (Windows has no power counters), and most offices pay a flat tariff, not exchange prices. Next step: state-level grids.

Live dashboard: https://cleanhour.vercel.app
Code (open source): https://github.com/Shraman123/cleanhour

#ClimateTech #AI #India #Sustainability #GreenAI #EnergyTransition
