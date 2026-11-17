# Timing rulebook for quantum computers

Oct 26, 2026 · @Someone

Today's quantum computers have no shared, checkable rulebook for time; this project would write one and build a tool that enforces it.

## The background

A normal computer can pause. If it is waiting for something, nothing is lost.

A quantum computer cannot pause. Its basic units, called qubits, are fragile and begin to fade the moment they are set up, like ice cream melting on a counter. Every operation has to happen on time, before the information fades.

## The problem

Think of baking a cake in a huge kitchen where five teams each work on their own clock. One measures in billionths of a second, one in millionths, one in thousandths, and the last thinks in minutes, like a delivery service. This works while each team sticks to its own schedule.

It gets hard when the recipe says: "taste the batter, and *depending on what you find*, add salt or add sugar." Nobody knows the result in advance. A quantum computer does the same thing when it measures a qubit and then picks its next step based on the answer.

The two choices take different amounts of time, so the rest of the kitchen no longer knows when the next step will happen, and the cake keeps melting. Companies handle this in three different ways today:

1. Make both choices take the same time, even if that means waiting.
2. Let each choice finish whenever it finishes, then make everyone meet up afterwards and accept a gap.
3. Hand the clock to the programmer and raise an alarm if someone is late.

These three ways do not agree. The same instruction can behave differently on different machines, and the software writing the instructions often cannot tell how long the pauses will be.

## Why this matters

Some tricks that protect qubits only work if you know exactly how long a pause lasts, the way a swing keeps going only if you push it at the right moment. If the pause length is unknown, those tricks fail.

The problem grows as quantum computers get bigger and start fixing their own errors, because that fixing has to happen on a very tight deadline.

## The proposed solution

Create a **shared rulebook for time** and a **checker** that uses it.

- **The rulebook** says what each part of the computer promises about timing. For example: "this step takes at most this long," "this answer arrives within this long," and "after this point, the plan can no longer be changed." Each branching instruction also states which of the three ways above it expects.
- **The checker** reads a program and the machine's promises, then answers one question *before* the program runs: "will anything arrive late or leave a gap nobody planned for?" It either says "safe" or points to the exact problem. It works like a spell-checker, but for timing.

The idea comes from other fields. Airplanes and cars already use timing rulebooks like this, but quantum computing has not borrowed them yet.

## How we would know it worked

We would test the checker on well-known quantum programs that use this "decide based on a result" pattern. It should catch every timing problem that really occurs, never wrongly call a broken program safe, and show how much the choice among the three ways changes the pauses.

## Honest limits

- Machine makers rarely publish their worst-case timings. If the promises are vague, the checker can only give vague answers.
- The idea has been compared with similar work only at the summary level, so it needs a full check before you commit to it.
