# Data dictionary

| Table | Main fields and meaning | Integrity rules |
|---|---|---|
| User | `username`, `email`, `password`, `role`, `phone` | Username unique; nonempty email unique; role is requester, volunteer, or coordinator; password stored as a hash |
| ItemCategory | `name`, `description` | Name unique |
| RepairRequest | `requester`, `category`, `item_name`, `description`, `status`, timestamps | Requester and category required; status follows the application workflow |
| RepairAssignment | `request`, `volunteer`, `assigned_by`, `assigned_at`, `notes` | One current assignment per request; volunteer selected from volunteer role |
| RepairSession | `request`, `volunteer`, `started_at`, `ended_at`, `findings`, `outcome` | End time cannot precede start time |
| SparePart | `name`, `unit`, `quantity`, `reorder_level` | Name unique; quantity cannot be negative |
| PartDonation | `part`, `donor`, `quantity`, `donated_at`, `notes` | Quantity greater than zero; stock increment in same transaction |
| PartUsage | `request`, `part`, `quantity`, `recorded_by`, `used_at` | Quantity greater than zero; stock decrement only when enough stock exists |
| RepairStatusHistory | `request`, `old_status`, `new_status`, `changed_by`, `changed_at`, `note` | PostgreSQL trigger records status updates automatically |
| RepairFeedback | `request`, `rating`, `comment`, `submitted_at` | One review per request; rating 1–5 |

Use `python manage.py sqlmigrate repairs 0001` to inspect the generated schema and `python manage.py sqlmigrate repairs 0002` to inspect the migration wrapper. The actual procedure and trigger SQL is in `repairs/migrations/0002_database_features.py`.
