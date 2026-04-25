# CAS Sourcing & Procurement Intelligence MVP v16.1

Streamlit MVP for CAS-number sourcing/procurement workflows.

## v16 focus

v16 builds on v15 with a stricter supplier-navigation workflow:

- Card-level CAS-gated product link expansion so search-page CAS noise does not validate unrelated product links.
- Wrong-CAS product identity rejection when a product page declares a different CAS in its identity block.
- Supplier search pages are treated as navigation/discovery pages, not verified price pages.
- Supplier-specific parser profiles are still used for quantity/price extraction once a product page is reached.
- Deferred product-name retry pass: after any supplier confirms the product name, earlier suppliers with weak CAS search pages can be retried using product-name probes.
- Product-level evidence exports include identity reason, observed CAS numbers, and price lead type for auditability.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Push the full folder structure to GitHub and deploy `app.py` on Streamlit Cloud.
Use Python 3.12 for the most stable deployment path.
