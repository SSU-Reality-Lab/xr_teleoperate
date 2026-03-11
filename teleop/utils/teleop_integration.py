"""
=== teleop_hand_and_arm.py Integration Example ===

This file shows the EXACT code changes needed in teleop_hand_and_arm.py to
integrate the Scene API client. Apply these as a diff.

Four integration points:
  1. Import (top of file)
  2. Client initialization (after sim mode DDS setup, ~line 300)
  3. Save/Discard handlers (replace existing DDS reset calls, ~lines 411-432)
  4. Cleanup (in finally block)
"""


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 1: Add import (after line 27, with other imports)
# ═══════════════════════════════════════════════════════════════════════════

# from teleop.utils.scene_client import SceneClient


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 2: Add CLI argument + initialize client
#           (after --waist-deadband-deg arg, ~line 131)
# ═══════════════════════════════════════════════════════════════════════════

# parser.add_argument('--scene-api-url', type=str, default='http://localhost:8200',
#                     help='URL of the Scene Control API server (unitree_sim_isaaclab)')


# After the sim mode DDS setup block (~line 302):
#
#     # Scene API client (for CS-Projects remote scene control)
#     scene_client = None
#     if args.sim and args.record:
#         from teleop.utils.scene_client import SceneClient
#         scene_client = SceneClient(server_url=args.scene_api_url)
#         if scene_client.is_available():
#             status = scene_client.get_status()
#             logger_mp.info(f"[Scene API] Connected. Scene {status.current_scene_index}/{status.total_scenes - 1}")
#         else:
#             logger_mp.warning("[Scene API] Server not available — falling back to DDS reset only")
#             scene_client = None


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 3: Replace save/discard handlers
#           (lines 411-432 in teleop_hand_and_arm.py)
# ═══════════════════════════════════════════════════════════════════════════

# BEFORE (original):
# ─────────────────
#     # record mode: discard
#     if args.record and RECORD_DISCARD:
#         RECORD_DISCARD = False
#         RECORD_RUNNING = False
#         recorder.discard_episode()
#         logger_mp.info("🗑️  Episode discarded. Press [s] to start a new recording.")
#         if args.sim:
#             publish_reset_category(1, reset_pose_publisher)
#
#     # record mode: toggle (start / save)
#     if args.record and RECORD_TOGGLE:
#         RECORD_TOGGLE = False
#         if not RECORD_RUNNING:
#             if recorder.create_episode():
#                 RECORD_RUNNING = True
#             else:
#                 logger_mp.error("Failed to create episode. Recording not started.")
#         else:
#             RECORD_RUNNING = False
#             recorder.save_episode()
#             if args.sim:
#                 publish_reset_category(1, reset_pose_publisher)

# AFTER (new):
# ────────────
#     # record mode: discard
#     if args.record and RECORD_DISCARD:
#         RECORD_DISCARD = False
#         RECORD_RUNNING = False
#         recorder.discard_episode()
#         logger_mp.info("🗑️  Episode discarded.")
#
#         if scene_client is not None:
#             # Ask server to reset the current scene to original positions
#             result = scene_client.reset_scene()
#             if result.success:
#                 logger_mp.info(f"[Scene API] Scene reset OK (scene {result.current_scene_index}). "
#                                "Press [s] to retry recording.")
#             else:
#                 logger_mp.error(f"[Scene API] Reset failed: {result.message}")
#                 # Fallback to DDS reset
#                 publish_reset_category(1, reset_pose_publisher)
#         elif args.sim:
#             publish_reset_category(1, reset_pose_publisher)
#
#     # record mode: toggle (start / save)
#     if args.record and RECORD_TOGGLE:
#         RECORD_TOGGLE = False
#         if not RECORD_RUNNING:
#             if recorder.create_episode():
#                 RECORD_RUNNING = True
#             else:
#                 logger_mp.error("Failed to create episode. Recording not started.")
#         else:
#             RECORD_RUNNING = False
#             recorder.save_episode()
#
#             if scene_client is not None:
#                 # Ask server to load the next scene
#                 result = scene_client.next_scene()
#                 if result.all_completed:
#                     logger_mp.info("══════════════════════════════════════")
#                     logger_mp.info("  ✅ ALL TASKS COMPLETED!")
#                     logger_mp.info("══════════════════════════════════════")
#                     # Option A: Graceful shutdown
#                     START = False
#                     STOP = True
#                     # Option B: Enter idle state (uncomment below, comment above)
#                     # logger_mp.info("Entering idle state. Press [q] to quit.")
#                 elif result.success:
#                     logger_mp.info(f"[Scene API] Next scene loaded (scene {result.current_scene_index}). "
#                                    "Press [s] to start recording.")
#                 else:
#                     logger_mp.error(f"[Scene API] Load next failed: {result.message}")
#                     # Fallback to DDS reset
#                     publish_reset_category(1, reset_pose_publisher)
#             elif args.sim:
#                 publish_reset_category(1, reset_pose_publisher)


# ═══════════════════════════════════════════════════════════════════════════
# CHANGE 4: Cleanup (in the finally block, before recorder.close())
# ═══════════════════════════════════════════════════════════════════════════

#     try:
#         if scene_client is not None:
#             scene_client.close()
#     except Exception as e:
#         logger_mp.error(f"Failed to close scene client: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# FULL DIFF SUMMARY (line references to original teleop_hand_and_arm.py)
# ═══════════════════════════════════════════════════════════════════════════
#
# --- a/teleop/teleop_hand_and_arm.py
# +++ b/teleop/teleop_hand_and_arm.py
#
# @@ line 27 (imports) @@
# +from teleop.utils.scene_client import SceneClient
#
# @@ line 131 (CLI args) @@
# +    parser.add_argument('--scene-api-url', type=str, default='http://localhost:8200',
# +                        help='URL of the Scene Control API server')
#
# @@ line 302 (after sim DDS setup) @@
# +        scene_client = None
# +        if args.sim and args.record:
# +            scene_client = SceneClient(server_url=args.scene_api_url)
# +            if scene_client.is_available():
# +                status = scene_client.get_status()
# +                logger_mp.info(f"[Scene API] Connected. Scene {status.current_scene_index}/{status.total_scenes - 1}")
# +            else:
# +                logger_mp.warning("[Scene API] Server not available — DDS-only fallback")
# +                scene_client = None
#
# @@ lines 411-432 (discard + save handlers) @@
# [Replace with the AFTER block shown above]
#
# @@ line 708 (finally block, before recorder.close()) @@
# +        try:
# +            if scene_client is not None:
# +                scene_client.close()
# +        except Exception as e:
# +            logger_mp.error(f"Failed to close scene client: {e}")
