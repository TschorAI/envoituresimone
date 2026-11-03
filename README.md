# envoituresimone

## Summary

- **What:** A web app for French drivers that gives the real cost of a refill or a trip. Use case A: the cheapest station near home, counting fuel bought plus fuel, wear and tear spent to drive there. Use case B: the cost of an A -> B route, fastest (with tolls) against toll-free, counting fuel, wear and tolls. Data: prix-carburants.gouv.fr (live station prices), Géoplateforme geocoding, OpenRouteService routing (OSM, avoid tollways). V1: SP95 and Diesel, editable consumption-by-speed curve per fuel, wear 0.10 EUR/km (optional, on by default), tolls 0.11 EUR/km estimate with a warning on short tolled stretches (Duplex A86). Out of scope: price forecasting, car models.
- **Status:** in progress
- **Created by:** leonardtschora
- **Created on:** 2026-11-03
- **Repository:** https://github.com/leonardtschora/envoituresimone
- **Shared drive and tasks:** personal project, own drive · task board https://github.com/users/leonardtschora/projects/18

## In short

_To be written, for someone who is not technical: the question, in two or three plain sentences,
and the answer so far (a few numbers at most)._

## What is here

_To be written: the deliverables a person would open (presentations, reports, figures, result
tables), one line each, with where to find them._

## Get started

Open Claude Code in this folder and ask it to set the project up. It runs `tools/setup.sh`, which
downloads the files from your drive and checks everything works. If the project needs passwords
(a database, a service), it tells you which ones and where to put them.

Please don't edit the files in `sources/`: they are kept exactly as we received them.

For the details (code, data, how it runs): `PROJECT.md`.
