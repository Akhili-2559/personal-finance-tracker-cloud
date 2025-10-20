from google.cloud import firestore

db = firestore.Client()

def add_expense(user_id, description, amount, category, date):
    doc_ref = db.collection("expenses").document()
    doc_ref.set({
        "user_id": user_id,
        "description": description,
        "amount": amount,
        "category": category,
        "date": date
    })

def get_expenses(user_id):
    expenses = db.collection("expenses").where("user_id", "==", user_id).order_by("date", direction=firestore.Query.DESCENDING).stream()
    return [e.to_dict() | {"id": e.id} for e in expenses]

def delete_expense(expense_id):
    db.collection("expenses").document(expense_id).delete()

def update_expense(expense_id, description, amount, category, date):
    db.collection("expenses").document(expense_id).update({
        "description": description,
        "amount": amount,
        "category": category,
        "date": date
    })
