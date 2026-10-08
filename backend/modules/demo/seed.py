"""Demo module seed helper."""

from sqlalchemy.orm import Session
from backend.seed.seed_data import seed_database, validate_seed_integrity


def run_seed(db: Session) -> bool:
    """Run initial database seeding if not yet populated."""
    return seed_database(db)


def check_seed_integrity(db: Session):
    """Run authoritative seed integrity verification."""
    return validate_seed_integrity(db)
