# Web IA Draft (Not in Work Yet)

Status: recorded only, not accepted into active implementation.
Source date: 2026-02-18

## Goal
Create a full information architecture skeleton early, even if many sections will not enter MVP.

## Public Zone
- `/`:
  - project overview
  - value proposition and examples/screenshots
  - contacts
  - links: privacy policy, offer/agreement, legal docs
  - auth block: registration/login or direct LK entry for already authorized users

## Client LK Zone
- `/lk/`:
  - client dashboard with global stats/analytics
  - examples: domains total, statuses, orders total, order statuses
  - links to detailed LK pages

- `/lk/my/`:
  - personal profile
  - passport data for domain registration
  - contacts
  - account links: VK/Google/Apple/etc.
  - actions: edit/update

- `/lk/domens/`:
  - domains table
  - pagination, filters, search
  - actions: add/edit/delete

- `/lk/domens/<ID>/`:
  - domain detail page
  - domain properties
  - DNS servers
  - actions: edit/delete

- `/lk/orders/`:
  - orders table
  - pagination, filters, search
  - actions: edit/delete

- `/lk/orders/<ID>/`:
  - order detail page
  - properties, price, status, related entities
  - actions: edit/delete

- `/lk/finances/`:
  - service payment
  - promo code input
  - link to payment history

- `/lk/finances/history`:
  - operations history
  - pagination, filters, search

- `/lk/documents`:
  - view offers/agreements
  - request original documents
  - request document copies to email
  - generate reconciliation report

## Admin Zone
- `/admin/`:
  - admin dashboard with global stats/analytics
  - examples: total clients, client statuses, domains by status, orders by status
  - links to detailed admin pages

- `/admin/users/`:
  - all clients table
  - pagination, filters, search

- `/admin/users/<ID>/`:
  - full client detail
  - properties, subscribed services, contracts, statistics

- `/admin/finances`:
  - global operations history across all users
  - pagination, filters, search

## Notes
- This is a draft IA/backlog entry.
- Route list is preliminary and can be refactored before implementation.
- Keep compatibility with current MVP (`/lk`, `/admin`, RBAC, event logs).
