from firebase_admin import firestore, storage
import firebase_admin
import decouple

FIREBASE_BUCKET = decouple.config("FIREBASE_BUCKET")

cred_obj = firebase_admin.credentials.Certificate("firebase-admin-key.json")
default_app = firebase_admin.initialize_app(cred_obj, options=None, name="FirestoreDB")
firestore = firestore.client(app=default_app)
bucket = storage.bucket(name=FIREBASE_BUCKET, app=default_app)

rules = bucket.lifecycle_rules
print(f"Lifecycle management rules for bucket DIGIMAP are {list(rules)}")
bucket.add_lifecycle_delete_rule(age=1)
bucket.patch()

rules = bucket.lifecycle_rules
print(f"Lifecycle management is enable for bucket DIGIMAP and the rules are {list(rules)}")