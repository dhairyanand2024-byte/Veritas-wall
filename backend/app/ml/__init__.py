# app/ml/__init__.py — silent background ML layer (Blueprint Section 3).
#
# Nothing here faces the user as a chatbot; the API calls it inline:
#   guard.py      -> automated de-anonymization sanitization (Stage 3)
#   embeddings.py -> dense vector for every cleared post (Stage 3/4)
#   semantic.py   -> pgvector nearest-neighbour lesson mapping (Stage 5)
