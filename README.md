# envoituresimone

## Summary

- **What:** A web app for French drivers that gives the real cost of a refill or a trip. Use case A: the cheapest station near home, counting fuel bought plus fuel, wear and tear spent to drive there. Use case B: the cost of an A -> B route, fastest (with tolls) against toll-free, counting fuel, wear and tolls. Data: prix-carburants.gouv.fr (live station prices), Géoplateforme geocoding, OpenRouteService routing (OSM, avoid tollways). V1 (use case A only): E10 and Diesel, editable consumption-by-speed curve per fuel, wear 0.10 EUR/km (optional, on by default). Use case B moves to v2, with real toll tariffs. Out of scope: price forecasting, car models.
- **Status:** in progress
- **Created by:** leonardtschora
- **Created on:** 2026-11-03
- **Repository:** https://github.com/TschorAI/envoituresimone
- **Shared drive and tasks:** personal project, own drive · task board https://github.com/users/leonardtschora/projects/18

## In short

Is the cheapest pump really the cheapest refill, once you count the drive there? And is the
toll-free road really cheaper than the motorway? The app answers the first for any French address, with today's prices. First runs around Paris: the cheapest diesel
pump was not the cheapest refill (about 1 EUR more, trip included).

## What is here

- **The price map**, public at https://simone.leonardtschora.com: every station in France,
  coloured by today's price, updated every hour.
- **Coming next:** the cheapest refill near you, trip included (built, not yet public), then the
  trip comparison with real tolls (v2). Ask Claude
  Code to start it.

## Get started

Open Claude Code in this folder and ask it to set the project up. It runs `tools/setup.sh`, which
downloads the files from your drive and checks everything works. If the project needs passwords
(a database, a service), it tells you which ones and where to put them.

Please don't edit the files in `sources/`: they are kept exactly as we received them.

For the details (code, data, how it runs): `PROJECT.md`.
