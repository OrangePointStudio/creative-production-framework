# Cost accounting

Keep estimates, measured consumption, paid invoices and allocated project costs separate. Missing cost is unknown, never zero. The reference CSV summarizer totals only entered quantities and paid allocations; it always leaves the complete project total unset because it cannot prove ledger completeness.

Minimum production ledger fields: run, timestamp, phase, provider, model/tool, unit, quantity, measurement source, estimated amount, actual debit, paid invoice amount, currency, allocation method and acceptance status. The small CLI CSV is an import starting point, not a complete accounting system.

Do not add credits from different providers or currencies. Cached model input and new output are distinct billing categories. Subscription use is not the same as a new cash payment or a list-price API equivalent. Record failed attempts and rejected outputs.

Separate setup, production and revision. Charge a shared master once. Report accepted output cost, revision time and sampled throughput. With a small sample, use median and worst observed result; do not claim a reliable p95.

Electricity uses measured whole-system energy and the actual tariff. GPU board power alone excludes the rest of the machine. Hardware allocation requires a documented asset value and useful production hours. Include storage, used software and paid contractors only on a stated basis.

For planning, show setup amortization over 5, 10 and 20 projects, separately from the first project's investment. A technical cost floor excluding human labour is not studio profit or a sale price. A commercial quote also accounts for support, revision obligations, risk, tax and margin.
