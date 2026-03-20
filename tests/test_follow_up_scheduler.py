"""Tests for follow-up scheduler — check_and_send_follow_ups logic."""

import asyncio
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


def _make_checkpoint_tuple(thread_id: str, values: dict):
    """Helper: create a mock CheckpointTuple with config and values."""
    mock_tuple = MagicMock()
    mock_tuple.config = {"configurable": {"thread_id": thread_id}}

    mock_snapshot = MagicMock()
    mock_snapshot.values = values
    return mock_tuple, mock_snapshot


class TestCheckAndSendFollowUps:
    """check_and_send_follow_ups sends message when all criteria are met."""

    @pytest.mark.asyncio
    async def test_sends_follow_up_when_criteria_met(self):
        """Should send follow-up when awaiting_reply=True, time elapsed, not sent yet."""
        old_time = time.time() - 3 * 3600  # 3 hours ago
        values = {
            "awaiting_reply": True,
            "follow_up_sent": False,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "5511999999999",
        }
        ckpt_tuple, snapshot = _make_checkpoint_tuple("thread-1", values)

        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_tuple]

        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message", return_value=True) as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_settings.FOLLOW_UP_MESSAGE = "Follow-up test"
            mock_settings.FOLLOW_UP_CHECK_INTERVAL_MINUTES = 30
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.return_value = snapshot

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 1
            mock_send.assert_called_once_with("5511999999999", "Follow-up test")
            mock_graph.update_state.assert_called_once_with(
                ckpt_tuple.config,
                {"follow_up_sent": True, "awaiting_reply": False},
            )

    @pytest.mark.asyncio
    async def test_skips_when_follow_up_already_sent(self):
        """Should not send if follow_up_sent=True."""
        old_time = time.time() - 3 * 3600
        values = {
            "awaiting_reply": True,
            "follow_up_sent": True,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "5511999999999",
        }
        ckpt_tuple, snapshot = _make_checkpoint_tuple("thread-1", values)

        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_tuple]

        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message") as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_settings.FOLLOW_UP_MESSAGE = "Follow-up test"
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.return_value = snapshot

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 0
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_em_atendimento_humano(self):
        """Should not send if em_atendimento_humano=True."""
        old_time = time.time() - 3 * 3600
        values = {
            "awaiting_reply": True,
            "follow_up_sent": False,
            "em_atendimento_humano": True,
            "last_activity": old_time,
            "chat_phone": "5511999999999",
        }
        ckpt_tuple, snapshot = _make_checkpoint_tuple("thread-1", values)

        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_tuple]

        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message") as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_settings.FOLLOW_UP_MESSAGE = "Follow-up test"
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.return_value = snapshot

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 0
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_awaiting_reply_false(self):
        """Should not send if awaiting_reply=False."""
        old_time = time.time() - 3 * 3600
        values = {
            "awaiting_reply": False,
            "follow_up_sent": False,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "5511999999999",
        }
        ckpt_tuple, snapshot = _make_checkpoint_tuple("thread-1", values)

        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_tuple]

        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message") as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_settings.FOLLOW_UP_MESSAGE = "Follow-up test"
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.return_value = snapshot

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 0
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_time_not_elapsed(self):
        """Should not send if less than FOLLOW_UP_HOURS have passed."""
        recent_time = time.time() - 30 * 60  # 30 min ago
        values = {
            "awaiting_reply": True,
            "follow_up_sent": False,
            "em_atendimento_humano": False,
            "last_activity": recent_time,
            "chat_phone": "5511999999999",
        }
        ckpt_tuple, snapshot = _make_checkpoint_tuple("thread-1", values)

        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_tuple]

        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message") as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_settings.FOLLOW_UP_MESSAGE = "Follow-up test"
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.return_value = snapshot

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 0
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self):
        """Should return 0 immediately when FOLLOW_UP_ENABLED=False."""
        with patch("src.scheduler.follow_up.settings") as mock_settings:
            mock_settings.FOLLOW_UP_ENABLED = False

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 0

    @pytest.mark.asyncio
    async def test_skips_when_no_checkpointer(self):
        """Should return 0 when graph has no checkpointer."""
        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_graph.checkpointer = None

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 0

    @pytest.mark.asyncio
    async def test_handles_multiple_threads(self):
        """Should process multiple threads and only send to eligible ones."""
        old_time = time.time() - 3 * 3600

        # Thread 1: eligible
        values_1 = {
            "awaiting_reply": True,
            "follow_up_sent": False,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "5511111111111",
        }
        ckpt1, snap1 = _make_checkpoint_tuple("thread-1", values_1)

        # Thread 2: not eligible (already sent)
        values_2 = {
            "awaiting_reply": True,
            "follow_up_sent": True,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "5522222222222",
        }
        ckpt2, snap2 = _make_checkpoint_tuple("thread-2", values_2)

        # Thread 3: eligible
        values_3 = {
            "awaiting_reply": True,
            "follow_up_sent": False,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "5533333333333",
        }
        ckpt3, snap3 = _make_checkpoint_tuple("thread-3", values_3)

        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt1, ckpt2, ckpt3]

        def get_state_side_effect(config):
            tid = config["configurable"]["thread_id"]
            return {"thread-1": snap1, "thread-2": snap2, "thread-3": snap3}[tid]

        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message", return_value=True) as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_settings.FOLLOW_UP_MESSAGE = "Follow-up test"
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.side_effect = get_state_side_effect

            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()

            assert count == 2
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_empty_thread_id(self):
        """Should skip checkpoint tuples with empty thread_id."""
        ckpt_tuple = MagicMock()
        ckpt_tuple.config = {"configurable": {"thread_id": ""}}
        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_tuple]
        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message") as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_graph.checkpointer = mock_checkpointer
            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()
            assert count == 0
            mock_graph.get_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_empty_chat_phone(self):
        """Should skip when chat_phone is empty."""
        old_time = time.time() - 3 * 3600
        values = {
            "awaiting_reply": True,
            "follow_up_sent": False,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "",
        }
        ckpt_tuple, snapshot = _make_checkpoint_tuple("thread-1", values)
        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_tuple]
        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message") as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.return_value = snapshot
            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()
            assert count == 0
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_exception_in_thread(self):
        """Should continue processing other threads when one raises."""
        old_time = time.time() - 3 * 3600
        ckpt_bad = MagicMock()
        ckpt_bad.config = {"configurable": {"thread_id": "bad-thread"}}

        values_good = {
            "awaiting_reply": True,
            "follow_up_sent": False,
            "em_atendimento_humano": False,
            "last_activity": old_time,
            "chat_phone": "5511111111111",
        }
        ckpt_good, snap_good = _make_checkpoint_tuple("good-thread", values_good)

        mock_checkpointer = MagicMock()
        mock_checkpointer.list.return_value = [ckpt_bad, ckpt_good]

        def get_state_effect(config):
            tid = config["configurable"]["thread_id"]
            if tid == "bad-thread":
                raise RuntimeError("corrupted state")
            return snap_good

        with (
            patch("src.scheduler.follow_up.graph") as mock_graph,
            patch("src.scheduler.follow_up.send_message", return_value=True) as mock_send,
            patch("src.scheduler.follow_up.settings") as mock_settings,
        ):
            mock_settings.FOLLOW_UP_ENABLED = True
            mock_settings.FOLLOW_UP_HOURS = 2
            mock_settings.FOLLOW_UP_MESSAGE = "Follow-up"
            mock_graph.checkpointer = mock_checkpointer
            mock_graph.get_state.side_effect = get_state_effect
            from src.scheduler.follow_up import check_and_send_follow_ups

            count = await check_and_send_follow_ups()
            assert count == 1  # good thread succeeded despite bad thread error

    @pytest.mark.asyncio
    async def test_follow_up_loop_runs_one_iteration(self):
        """follow_up_loop calls check_and_send_follow_ups after sleeping."""
        from src.scheduler.follow_up import follow_up_loop

        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise asyncio.CancelledError()
            return 0

        with (
            patch("src.scheduler.follow_up.settings") as mock_settings,
            patch("src.scheduler.follow_up.check_and_send_follow_ups", side_effect=mock_check),
            patch("src.scheduler.follow_up.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.FOLLOW_UP_CHECK_INTERVAL_MINUTES = 1
            mock_settings.FOLLOW_UP_HOURS = 2
            with pytest.raises(asyncio.CancelledError):
                await follow_up_loop()
