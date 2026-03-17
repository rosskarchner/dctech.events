# Frontend Implementation Plan: dctech.events (v2)

This document outlines the requirements for the new frontend of **dctech.events**, a community-curated, wiki-style calendar for tech events in the DC/MD/VA area.

## 1. Core Philosophy: "The Week is the Wiki"

Unlike traditional event platforms, **there are no event-detail pages.**
- **Navigation:** Users browse by **Week** (e.g., `/weeks/2026-W10`).
- **Interaction:** Clicking an event name or "Register" button links **directly out** to the external source URL.
- **Contribution:** The Week view is the primary interface for creating, editing, and auditing events.

---

## 2. Architecture & Tech Stack

- **Framework:** Next.js (App Router) or Vite + React.
- **Styling:** Tailwind CSS (Modern, clean, "Wiki-like" aesthetic).
- **State Management:** TanStack Query (React Query) for efficient API synchronization.
- **Auth:** AWS Amplify Auth (v6) to interface with the existing Cognito pool.
- **API Base URL:** `https://sdaa1b4o6h.execute-api.us-east-1.amazonaws.com/`

---

## 3. Key Views & API Integration

### A. The Weekly Calendar (`/weeks/[weekId]`)
The heart of the application. Shows all events for a specific ISO week.
- **Route:** `/weeks/YYYY-WNN` (e.g., `/weeks/2026-W12`).
- **Data:** Call `GET /weeks/{weekId}/events`.
- **Synthetic Logic:** If the API returns a 404 or a "synthetic" record, calculate the Monday–Sunday date range locally from the `weekId` to ensure the page always renders.
- **Navigation:** "Previous" and "Next" week buttons using ISO week math.

### B. The "Upcoming" Home Page (`/`)
A simplified feed of events from the current and future weeks.
- **Data:** Call `GET /events/upcoming`.
- **Logic:** Direct users toward the Weekly Wiki pages for editing or contribution.

### C. Site-wide History (`/history`)
A chronological log of all community edits.
- **Data:** Call `GET /history`.
- **Logic:** Provides transparency into who edited what and when.

---

## 4. Wiki Features (Authenticated Users Only)

Since there are no event pages, all contributor actions occur via **Modals** or **Inline Panels** launched from the Week view.

### I. The Edit Modal (`PUT /events/{eventId}`)
- **Source-Lock Enforcement:** Respect the `sourceLocked` attribute from the API.
- **UI:** If `sourceLocked: true`, disable inputs for `date`, `time`, `url`, and `groupId`. Show a tooltip: *"Locked to iCal source."*
- **Fields:** Users can always update `name`, `description`, and `categoryId`.

### II. History & Rollback Modal
- **Data:** Call `GET /events/{eventId}/history`.
- **UI:** A vertical list of versions.
- **Action:** A "Restore" button calls `POST /events/{eventId}/rollback` with the specific `versionId`.

### III. Duplicate Marking
- **Action:** `POST /events/{eventId}/duplicate` with a `canonicalEventId`.
- **Feedback:** Upon success, the event is immediately hidden from the Week view (the API filters out duplicates by default).

---

## 5. Authentication & Permissions

| Role | Access |
| :--- | :--- |
| **Anonymous** | View Weeks, View Upcoming, Click External Links, View History. |
| **Contributor** | All "Anonymous" features + Create Event, Edit Event, Rollback, Mark Duplicate. |

**Cognito Configuration:**
- **User Pool ID:** `us-east-1_8Ay4dTt8j`
- **Client ID:** `58j1h73i72v1kaim503bk2amgb`

---

## 6. Development Milestones

1.  **ISO Week Routing:** Build the navigator logic for `/weeks/YYYY-WNN`.
2.  **API Integration:** Connect the Week view to the dynamic API.
3.  **Auth Flow:** Implement Login/Logout using the existing Cognito pool.
4.  **The Wiki Editor:** Build the Edit and History modals with Source-Lock logic.
5.  **Audit & Search:** Build the site-wide history feed and client-side list filtering.

---

## 7. Environment Variables
```bash
NEXT_PUBLIC_API_URL=https://sdaa1b4o6h.execute-api.us-east-1.amazonaws.com
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_8Ay4dTt8j
NEXT_PUBLIC_COGNITO_CLIENT_ID=58j1h73i72v1kaim503bk2amgb
```
