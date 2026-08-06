# Mental Omega Randomizer - Archipelago Integration

## Overview

We want to integrate **Archipelago Multiworld** into the existing **Mental Omega Randomizer**.

The Randomizer already contains almost everything required to support Archipelago:

- Mission generation
- Reward generation
- Objective tracking
- Mission completion tracking
- Reward application
- Grid generation
- Launcher UI
- Save/Load settings
- Debug.log monitoring

**DO NOT reinvent existing systems.**

Your first task is to **study the complete codebase**, understand how the Randomizer currently works and integrate Archipelago into the existing architecture while keeping standalone mode fully functional.

The goal is **NOT** to rewrite the Randomizer.

The goal is to **embed Archipelago into it**.

---

# Required Research

Before implementing anything, study the following:

## Our Repository

https://github.com/Heinki/Mental-Omega-Randomizer

Understand:

- launcher architecture
- mission generation
- reward generation
- reward pools
- objective tracking
- debug.log parser
- mission completion detection
- grid generation
- settings
- yaml generation
- save/load logic

Do not duplicate existing logic.

Reuse it whenever possible.

---

## Archipelago

Study the official documentation.

https://github.com/ArchipelagoMW/Archipelago

https://github.com/ArchipelagoMW/Archipelago/tree/main/docs

Important documentation:

- Adding Games
- World API
- APWorld Specification
- Options API
- Network Protocol
- APWorld Dev FAQ

Also study:

https://github.com/TheCondor07/Starcraft2ArchipelagoData

This is an RTS integration and should be used as reference where applicable.

---

# Overall Architecture

The Randomizer stays the primary application.

Archipelago becomes an integrated feature.

Standalone Randomizer continues to function exactly as today.

When connected to Archipelago:

- Archipelago controls item placement
- Randomizer controls gameplay
- Randomizer detects checks
- Randomizer applies received rewards
- Randomizer launches missions
- Randomizer displays progression

---

# Repository Structure

Create a dedicated Archipelago module.

Example:

```
Mental-Omega-Randomizer

    Archipelago/
        APWorld/
        Client/
        Networking/
        Models/
        Serialization/
        Resources/
        Utils/

```

Keep Archipelago code isolated.

Do NOT spread AP logic randomly across the project.

---

# APWorld

Implement a complete APWorld.

It must contain:

- Items
- Locations
- Regions
- Rules
- Options
- Slot Data
- Completion Condition
- YAML generation
- Packaging

Generate a proper .apworld.

---

# Embedded Client

Do NOT create an external launcher.

Integrate the client directly into the Randomizer.

Create a new tab:

```
Grid Mode
Settings
Advanced
Archipelago
```

The Archipelago tab becomes the integrated client.

---

# Archipelago Tab

The tab should contain:

Connection

- Server
- Port
- Slot Name
- Password
- Connect
- Disconnect

Status

- Connected
- Connecting
- Disconnected

Information

- Received Items
- Sent Checks
- Chat/System Messages
- Connection Log

History

- Received Rewards
- Sent Rewards
- Mission Checks
- Objective Checks

Connection should support

- ws
- wss

Reconnect support should be implemented.

---

# Existing Tracking

Reuse existing systems.

We already detect:

- Objectives
- Mission completion

This is done via

debug.log

Do NOT replace this.

Use the existing implementation.

There is also already a manual

"Mark Mission Complete"

button.

Reuse this as fallback.

---

# What counts as an Archipelago Check

ONLY:

Mission Objectives

Mission Completion

Nothing else.

---

# Reward Locations

The Randomizer already supports multiple rewards.

Archipelago locations become reward slots.

Example

If objective rewards = 3

```
Allied 06
    Objective 1
        Reward 1
        Reward 2
        Reward 3
```

If mission rewards = 2

```
Mission Complete
    Reward 1
    Reward 2
```

Completing an objective sends every reward slot.

Exactly the same for mission completion.

---

# Existing Reward System

DO NOT implement a second reward system.

Reuse the Randomizer reward implementation.

Archipelago decides

WHAT reward is placed.

The Randomizer decides

HOW it is applied.

---

# Item Pool

The APWorld should use the existing Mental Omega reward pool.

Do not invent a second item system.

Study the reward implementation already inside the Randomizer.

Reuse everything possible.

---

# Goal Conditions

Classic

Finish the final mission.

Mission List

Finish every mission.

Grid Mode

Finish the final mission in the bottom-right of the generated grid.

The existing Randomizer already knows these conditions.

Reuse them.

---

# Mission Unlocking

Archipelago DOES NOT unlock missions.

The Randomizer already handles

- Grid traversal
- Unlock progression
- Mission availability

Leave this unchanged.

---

# Connection Flow

Connect

↓

Receive slot_data

↓

Validate version

↓

Load Randomizer configuration

↓

Lock configuration

↓

Begin tracking

↓

Receive items

↓

Apply rewards

↓

Report checks

---

# Slot Data

Store all deterministic Randomizer information inside slot_data.

Examples

- Randomizer seed
- Mode
- Grid information
- Campaign selection
- Goal
- Reward count
- Reward settings
- Enabled reward pool
- Version
- Other required deterministic settings

The launcher should reconstruct or validate the Randomizer configuration from slot_data.

The player should never accidentally connect using the wrong Randomizer configuration.

---

# Configuration Locking

While connected

ALL gameplay-affecting settings become read-only.

Examples

- reward count
- reward pool
- campaigns
- mode
- grid
- seed
- yaml
- enabled items
- progression settings

Changing these must be impossible.

Disconnecting restores normal editing.

Standalone mode behaves exactly like today.

---

# YAML

Reuse the existing YAML generation UI.

Extend it.

Allow

- Generate
- Save
- Load

Archipelago YAMLs.

Do not create a second UI if unnecessary.

---

# Existing Settings

The Randomizer already allows

enable

disable

reward configuration

Reuse these settings inside Archipelago.

Do not duplicate them.

---

# APWorld Generation

Generate

- YAML
- APWorld
- Slot Data

Everything should be generated directly from the Randomizer configuration.

---

# Networking

Support

- ws
- wss

Implement

- reconnect
- reconnect recovery
- item synchronization
- duplicate protection

Persist

- received item index
- completed locations

Handle reconnects safely.

---

# Item Placement

Archipelago owns placement.

Option A

The APWorld directly places Mental Omega rewards.

Do NOT use generic reward tokens.

The APWorld should understand the Mental Omega reward pool.

---

# Existing Randomizer Responsibilities

Remain unchanged.

The Randomizer still handles

- launching missions
- mission generation
- reward application
- UI
- debug.log parsing
- mission tracking
- objective tracking
- grid

Archipelago simply provides network synchronization.

---

# Standalone Mode

Nothing should break.

If Archipelago is disconnected

the launcher should behave exactly like today's Randomizer.

No regressions.

---

# Implementation Order

Do NOT attempt everything at once.

Work incrementally.

## Phase 1

Repository audit

Understand the codebase.

Document architecture.

---

## Phase 2

Design AP integration.

Choose integration points.

Minimize duplicated code.

---

## Phase 3

Implement a minimal APWorld.

Very small item/location set.

End-to-end testing.

---

## Phase 4

Implement embedded client.

Connect successfully.

Receive slot_data.

Display status.

---

## Phase 5

Hook objective detection.

Report objective checks.

---

## Phase 6

Hook mission completion.

Report mission completion.

---

## Phase 7

Receive items.

Apply rewards using the existing reward system.

---

## Phase 8

Generate complete APWorld.

Full reward pool.

Full location pool.

---

## Phase 9

YAML integration.

Settings integration.

Configuration locking.

---

## Phase 10

Packaging.

Generate

.apworld

and all required artifacts.

---

## Phase 11

Testing

Test

- reconnect
- duplicate packets
- reconnect after crash
- objective spam
- mission completion
- reward synchronization
- multiple reward slots
- standalone mode
- AP mode

---

# Performance

Do not introduce unnecessary allocations.

Avoid duplicated data.

Reuse existing collections where possible.

Avoid polling if event-driven solutions already exist.

Keep the launcher responsive.

---

# Code Quality

- Keep modules small.
- Keep networking isolated.
- Avoid duplicate implementations.
- Reuse existing Randomizer logic.
- Follow existing project architecture.
- Keep standalone compatibility.
- Write maintainable code.
- Document non-obvious systems.

---

# Important

Before implementing any feature:

1. Study the existing Randomizer implementation.
2. Find whether the functionality already exists.
3. Extend existing systems instead of replacing them.
4. Keep the existing standalone Randomizer fully functional.
5. Build the integration step by step and verify each milestone before moving on.
6. If an architectural uncertainty is discovered, stop and document it before making assumptions.

The goal is a clean, maintainable Archipelago integration that feels like a native part of the Mental Omega Randomizer rather than an external add-on.