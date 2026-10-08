# Relational schema and normalization

The 10 application tables are:

1. `User(id PK, username UNIQUE, email UNIQUE WHEN NONEMPTY, password_hash, role, phone, ...)`
2. `ItemCategory(id PK, name UNIQUE, description)`
3. `RepairRequest(id PK, requester_id FK→User, category_id FK→ItemCategory, item_name, description, status, created_at, updated_at, completed_at)`
4. `RepairAssignment(id PK, request_id FK→RepairRequest UNIQUE, volunteer_id FK→User, assigned_by_id FK→User, assigned_at, notes)`
5. `RepairSession(id PK, request_id FK→RepairRequest, volunteer_id FK→User, started_at, ended_at, findings, outcome)`
6. `SparePart(id PK, name UNIQUE, unit, quantity, reorder_level)`
7. `PartDonation(id PK, part_id FK→SparePart, donor_id FK→User, quantity, donated_at, notes)`
8. `PartUsage(id PK, request_id FK→RepairRequest, part_id FK→SparePart, recorded_by_id FK→User, quantity, used_at)`
9. `RepairStatusHistory(id PK, request_id FK→RepairRequest, changed_by_id FK→User NULL, old_status, new_status, changed_at, note)`
10. `RepairFeedback(id PK, request_id FK→RepairRequest UNIQUE, rating, comment, submitted_at)`

All non-key facts describe the row's primary key. Category names, volunteer details, and part names live in their own tables and are referenced by keys. Donation and usage events are separate from current stock. This removes repeating groups and transitive dependencies, meeting 3NF for the application tables. `SparePart.quantity` is a maintained stock balance for fast availability checks; transactions keep it consistent with donation and usage events.

Foreign keys are indexed by Django. An additional composite index covers request status and creation date. Constraints enforce positive event quantities, a rating of 1–5, and session end time after start. The PostgreSQL trigger audits every status update. The view `repair_summary` joins requests, categories, and usage records.
