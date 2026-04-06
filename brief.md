# Overall design
App Overview: Clinical Recall Assistant
1. The Vision & Vibe
The app is a high-performance study tool for paramedics. It needs to feel clinical, reliable, and distraction-free. 
 * Visual Style: Clean lines, ample white space (or a high-contrast Dark Mode)
 * Color Language: Use medical status colors—Success Green, Caution Yellow, and Critical Red—to signal knowledge mastery and urgency.
2. Core Screen Requirements
A. The Command Dashboard (Home)
The landing page where the user assesses their "Readiness."
 * Knowledge Heatmap: A central visual grid representing ACTAS guideline chapters (e.g., Cardiac, Trauma, Respiratory). Blocks glow Red (unstudied/low scores) to Green (mastered).
 * Performance Metrics: Small, punchy cards showing "Current Streak," "Average Accuracy," and "Suggested Next Topic."
 * The "Start" Button: A high-visibility primary action button to start a session.
B. The Library & Pipeline Manager
The "behind-the-scenes" area where data is managed.
 * Source Cards: Clean list of connected sources (Google Docs, Notability PDF, ACTAS Web URL).
 * Sync Indicators: Small progress bars or "Last Synced" timestamps.
 * The "Cleaning" Feed: A toggleable view to show how the AI is "fixing" handwritten notes into clean Markdown text.
C. The Active Recall Quiz (Focus Mode)
A minimalist interface designed for deep concentration.
 * Question Area: Large, bold text for the prompt.
 * Response Input: A wide, clean text area for typing answers.
 * The "Reveal" Mechanism: A clear secondary button for self-grading if the user doesn't want to type.
 * Progress Bar: A thin, non-intrusive bar at the top showing progress through the current set.
D. The Feedback & Citation Panel
The most critical screen for learning. It appears after an answer is submitted.
 * Split-Screen View: The left side shows the user’s answer; the right side shows the AI Critique.
 * The "From the Source" Snippet: A highlighted box containing the exact text from the ACTAS guidelines or personal notes.
 * Source Footnotes: Clickable links that look like medical citations (e.g., Ref: ACTAS CMG 14.1).
3. Navigation Strategy
 * Persistent Sidebar: A slim, iconic sidebar on the left for switching between Dashboard, Library, Quiz History, and Settings.
 * Universal Search: A top-level search bar to quickly find any specific guideline or note without starting a quiz.
Design Goals for the Agent
 * Reduce Friction: The user should be able to start a quiz in under two clicks from launch.
 * Highlight Sources: The clinical guidelines must always feel like the "primary authority."
 * Gamify Mastery: Use the Heatmap to make "filling the grid with green" the primary psychological driver for the user.