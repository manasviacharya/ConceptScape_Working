"""Apply the application schema migrations without starting the API."""
from storage.database import init_db


if __name__ == "__main__":
    init_db()
    print("ConceptScape database migrations applied.")
