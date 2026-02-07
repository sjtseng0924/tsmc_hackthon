from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import Contact

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

# Pydantic schemas
class ContactCreate(BaseModel):
    name: str
    email: str
    discord_id: Optional[str] = None
    department: Optional[str] = None

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    discord_id: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[int] = None

class ContactResponse(BaseModel):
    id: int
    name: str
    email: str
    discord_id: Optional[str]
    department: Optional[str]
    is_active: int
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[ContactResponse])
def list_contacts(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List all contacts."""
    query = db.query(Contact)
    if active_only:
        query = query.filter(Contact.is_active == 1)
    return query.all()

@router.get("/search", response_model=List[ContactResponse])
def search_contacts(
    query: str,
    threshold: float = 0.3,
    db: Session = Depends(get_db)
):
    """
    Search contacts using fuzzy matching.
    
    Args:
        query: Search term (can have typos)
        threshold: Minimum similarity score (0-1), default 0.3
    """
    sql = text("""
        SELECT id, name, email, department, is_active,
               similarity(LOWER(name), LOWER(:query)) as score
        FROM contacts
        WHERE is_active = 1
          AND similarity(LOWER(name), LOWER(:query)) > :threshold
        ORDER BY score DESC
        LIMIT 10
    """)
    
    results = db.execute(sql, {"query": query, "threshold": threshold}).fetchall()
    
    return [
        ContactResponse(
            id=r.id,
            name=r.name,
            email=r.email,
            department=r.department,
            is_active=r.is_active
        )
        for r in results
    ]

@router.post("/", response_model=ContactResponse)
def create_contact(
    contact: ContactCreate,
    db: Session = Depends(get_db)
):
    """Create a new contact."""
    # Check if email already exists
    existing = db.query(Contact).filter(Contact.email == contact.email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Contact with email {contact.email} already exists")
    
    # Check if discord_id already exists (if provided)
    if contact.discord_id:
        existing_discord = db.query(Contact).filter(Contact.discord_id == contact.discord_id).first()
        if existing_discord:
            raise HTTPException(status_code=400, detail=f"Contact with discord_id {contact.discord_id} already exists")
    
    db_contact = Contact(
        name=contact.name,
        email=contact.email,
        discord_id=contact.discord_id,
        department=contact.department,
        is_active=1
    )
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    contact: ContactUpdate,
    db: Session = Depends(get_db)
):
    """Update a contact."""
    db_contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Update fields
    if contact.name is not None:
        db_contact.name = contact.name
    if contact.email is not None:
        # Check if new email conflicts with another contact
        existing = db.query(Contact).filter(
            Contact.email == contact.email,
            Contact.id != contact_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Email {contact.email} is already used by another contact")
        db_contact.email = contact.email
    if contact.discord_id is not None:
        # Check if new discord_id conflicts with another contact
        existing = db.query(Contact).filter(
            Contact.discord_id == contact.discord_id,
            Contact.id != contact_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Discord ID {contact.discord_id} is already used by another contact")
        db_contact.discord_id = contact.discord_id
    if contact.department is not None:
        db_contact.department = contact.department
    if contact.is_active is not None:
        db_contact.is_active = contact.is_active
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.delete("/{contact_id}")
def delete_contact(
    contact_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db)
):
    """
    Delete a contact.
    
    Args:
        contact_id: ID of the contact to delete
        soft_delete: If True, mark as inactive instead of deleting (default: True)
    """
    db_contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    if soft_delete:
        db_contact.is_active = 0
        db.commit()
        return {"message": f"Contact {db_contact.name} marked as inactive"}
    else:
        db.delete(db_contact)
        db.commit()
        return {"message": f"Contact {db_contact.name} permanently deleted"}
