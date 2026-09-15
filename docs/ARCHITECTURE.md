# Architecture

Cloudflare Worker + D1 is the canonical control/data plane. Heavy browser verification is an optional outbound Win11 worker. Source acquisition is push-first: webhook/email/RSS/API/conditional HTTP before browser/OCR. The worker cron acts as a bounded dispatcher only.
