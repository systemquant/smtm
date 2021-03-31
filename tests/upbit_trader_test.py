import os
import unittest
from urllib.parse import urlencode
from smtm import UpbitTrader
from unittest.mock import *


class UpditTraderTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_send_request_should_call_worker_post_task_correctly(self):
        trader = UpbitTrader()
        trader.worker = MagicMock()

        trader.send_request("mango", "banana")

        trader.worker.post_task.assert_called_once()
        called_arg = trader.worker.post_task.call_args[0][0]
        self.assertEqual(called_arg["runnable"], trader._excute_order)
        self.assertEqual(called_arg["request"], "mango")
        self.assertEqual(called_arg["callback"], "banana")

    def test_send_account_info_request_should_call_worker_post_task_correctly(self):
        trader = UpbitTrader()
        trader.worker = MagicMock()

        trader.send_account_info_request("banana")

        trader.worker.post_task.assert_called_once()
        called_arg = trader.worker.post_task.call_args[0][0]
        self.assertEqual(called_arg["runnable"], trader._excute_query)
        self.assertEqual(called_arg["callback"], "banana")

    def test__excute_order_handle_task_correctly(self):
        dummy_task = {
            "request": {"id": "apple", "price": 500, "amount": 0.0001, "type": "buy"},
            "callback": "kiwi",
        }
        trader = UpbitTrader()
        trader._send_order = MagicMock(return_value={"uuid": "mango"})
        trader._create_success_result = MagicMock(return_value="banana")
        trader._start_timer = MagicMock()

        trader._excute_order(dummy_task)

        trader._send_order.assert_called_once_with(trader.MARKET, True, 500, 0.0001)
        trader._create_success_result.assert_called_once_with(dummy_task["request"])
        trader._start_timer.assert_called_once()
        self.assertEqual(trader.request_map["apple"]["uuid"], "mango")
        self.assertEqual(trader.request_map["apple"]["callback"], "kiwi")
        self.assertEqual(trader.request_map["apple"]["result"], "banana")

    def test__excute_order_should_call_callback_with_error_when__send_order_return_None(self):
        dummy_task = {
            "request": {"id": "apple", "price": 500, "amount": 0.0001, "type": "buy"},
            "callback": MagicMock(),
        }
        trader = UpbitTrader()
        trader._send_order = MagicMock(return_value=None)
        trader._create_success_result = MagicMock(return_value="banana")
        trader._start_timer = MagicMock()

        trader._excute_order(dummy_task)

        dummy_task["callback"].assert_called_once_with("error!")
        trader._send_order.assert_called_once_with(trader.MARKET, True, 500, 0.0001)
        trader._create_success_result.assert_not_called()
        trader._start_timer.assert_not_called()
        self.assertEqual(len(trader.request_map), 0)

    def test__excute_query_handle_task_correctly(self):
        dummy_task = {
            "request": {"id": "apple", "price": 500, "amount": 0.0001, "type": "buy"},
            "callback": MagicMock(),
        }
        dummy_respone = [
            {"currency": "KRW", "balance": 123456789},
            {"currency": "APPLE", "balance": 500, "avg_buy_price": 23456},
        ]
        trader = UpbitTrader()
        trader._query_account = MagicMock(return_value=dummy_respone)

        trader._excute_query(dummy_task)

        trader._query_account.assert_called_once()
        dummy_task["callback"].assert_called_once_with(
            {"balance": 123456789, "asset": {"APPLE": (23456, 500)}}
        )

    def test__excute_query_handle_None_response(self):
        dummy_task = {
            "request": {"id": "apple", "price": 500, "amount": 0.0001, "type": "buy"},
            "callback": MagicMock(),
        }
        dummy_respone = None
        trader = UpbitTrader()
        trader._query_account = MagicMock(return_value=dummy_respone)

        trader._excute_query(dummy_task)

        trader._query_account.assert_called_once()
        dummy_task["callback"].assert_called_once_with("error!")

    def test__create_success_result_return_correct_result(self):
        dummy_request = {"id": "mango", "type": "banana", "price": 500, "amount": 0.12345}
        trader = UpbitTrader()
        success_result = trader._create_success_result(dummy_request)

        self.assertEqual(success_result["request"]["id"], dummy_request["id"])
        self.assertEqual(success_result["type"], dummy_request["type"])
        self.assertEqual(success_result["price"], dummy_request["price"])
        self.assertEqual(success_result["amount"], dummy_request["amount"])
        self.assertEqual(success_result["msg"], "success")

    @patch("threading.Timer")
    def test_start_timer_should_start_Timer(self, mock_timer):
        trader = UpbitTrader()
        trader.worker = MagicMock()

        trader._start_timer()

        mock_timer.assert_called_once_with(trader.RESULT_CHECKING_INTERVAL, ANY)
        callback = mock_timer.call_args[0][1]
        callback()
        trader.worker.post_task.assert_called_once_with({"runnable": trader._query_order_result})

    def test_stop_timer_should_call_cancel(self):
        trader = UpbitTrader()
        timer_mock = MagicMock()
        trader.timer = timer_mock

        trader._stop_timer()

        timer_mock.cancel.assert_called_once()
        self.assertEqual(trader.timer, None)

    def test__query_order_result_should_call_callback_and_keep_waiting_request(self):
        dummy_result = [
            {"uuid": "mango", "state": "done", "created_at": "today"},
            {"uuid": "banana", "state": "wait", "created_at": "tomorrow"},
            {"uuid": "apple", "state": "cancel", "created_at": "yesterday"},
        ]
        dummy_request_mango = {
            "uuid": "mango",
            "request": {"id": "mango_id"},
            "callback": MagicMock(),
            "result": {"id": "mango_result"},
        }
        dummy_request_banana = {
            "uuid": "banana",
            "request": {"id": "banana_id"},
            "callback": MagicMock(),
            "result": {"id": "banana_result"},
        }
        dummy_request_apple = {
            "uuid": "apple",
            "request": {"id": "apple_id"},
            "callback": MagicMock(),
            "result": {"id": "apple_result"},
        }
        trader = UpbitTrader()
        trader._query_order_list = MagicMock(return_value=dummy_result)
        trader._stop_timer = MagicMock()
        trader._start_timer = MagicMock()
        trader.request_map["mango"] = dummy_request_mango
        trader.request_map["banana"] = dummy_request_banana
        trader.request_map["apple"] = dummy_request_apple

        trader._query_order_result(None)

        mango_result = dummy_request_mango["callback"].call_args[0][0]
        self.assertEqual(mango_result["date_time"], "today")
        self.assertEqual(mango_result["id"], "mango_result")
        dummy_request_mango["callback"].assert_called_once()

        apple_result = dummy_request_apple["callback"].call_args[0][0]
        self.assertEqual(apple_result["date_time"], "yesterday")
        self.assertEqual(apple_result["id"], "apple_result")
        dummy_request_mango["callback"].assert_called_once()

        self.assertEqual(len(trader.request_map), 1)
        self.assertEqual(trader.request_map["banana"]["request"]["id"], "banana_id")
        trader._stop_timer.assert_called_once()
        trader._start_timer.assert_called_once()

    def test__query_order_result_should_NOT_start_timer_when_no_request_remains(self):
        dummy_result = [
            {"uuid": "mango", "state": "done", "created_at": "today"},
        ]
        dummy_request_mango = {
            "uuid": "mango",
            "request": {"id": "mango_id"},
            "callback": MagicMock(),
            "result": {"id": "mango_result"},
        }
        trader = UpbitTrader()
        trader._query_order_list = MagicMock(return_value=dummy_result)
        trader._stop_timer = MagicMock()
        trader._start_timer = MagicMock()
        trader.request_map["mango"] = dummy_request_mango

        trader._query_order_result(None)

        mango_result = dummy_request_mango["callback"].call_args[0][0]
        self.assertEqual(mango_result["date_time"], "today")
        self.assertEqual(mango_result["id"], "mango_result")
        dummy_request_mango["callback"].assert_called_once()

        self.assertEqual(len(trader.request_map), 0)
        trader._stop_timer.assert_called_once()
        trader._start_timer.assert_not_called()

    @patch("requests.post")
    def test__send_order_should_send_correct_limit_order(self, mock_requests):
        trader = UpbitTrader()

        class DummyResponse:
            pass

        dummy_response = DummyResponse()
        dummy_response.raise_for_status = MagicMock()
        dummy_response.json = MagicMock(return_value="mango_response")
        mock_requests.return_value = dummy_response
        trader._create_jwt_token = MagicMock(return_value="mango_token")
        trader._create_limit_order_query = MagicMock(return_value="mango_query")

        response = trader._send_order("mango", True, 500, 0.555)

        self.assertEqual(response, "mango_response")
        dummy_response.raise_for_status.assert_called_once()
        dummy_response.json.assert_called_once()
        trader._create_limit_order_query.assert_called_once_with("mango", True, 500, 0.555)
        trader._create_jwt_token.assert_called_once_with(
            trader.ACCESS_KEY, trader.SECRET_KEY, "mango_query"
        )
        mock_requests.assert_called_once_with(
            trader.SERVER_URL + "/v1/orders",
            params="mango_query",
            headers={"Authorization": "Bearer mango_token"},
        )

    @patch("requests.post")
    def test__send_order_should_send_correct_market_price_buy_order(self, mock_requests):
        trader = UpbitTrader()

        class DummyResponse:
            pass

        dummy_response = DummyResponse()
        dummy_response.raise_for_status = MagicMock()
        dummy_response.json = MagicMock(return_value="mango_response")
        mock_requests.return_value = dummy_response
        trader._create_jwt_token = MagicMock(return_value="mango_token")
        trader._create_market_price_order_query = MagicMock(return_value="mango_query")

        response = trader._send_order("mango", True, 500)

        self.assertEqual(response, "mango_response")
        trader._create_market_price_order_query.assert_called_once_with("mango", price=500)

    @patch("requests.post")
    def test__send_order_should_send_correct_market_sell_order(self, mock_requests):
        trader = UpbitTrader()

        class DummyResponse:
            pass

        dummy_response = DummyResponse()
        dummy_response.raise_for_status = MagicMock()
        dummy_response.json = MagicMock(return_value="mango_response")
        mock_requests.return_value = dummy_response
        trader._create_jwt_token = MagicMock(return_value="mango_token")
        trader._create_market_price_order_query = MagicMock(return_value="mango_query")

        response = trader._send_order("mango", False, volume=0.55)

        self.assertEqual(response, "mango_response")
        trader._create_market_price_order_query.assert_called_once_with("mango", volume=0.55)

    @patch("requests.post")
    def test__send_order_should_NOT_send_invaild_order(self, mock_requests):
        trader = UpbitTrader()

        class DummyResponse:
            pass

        dummy_response = DummyResponse()
        dummy_response.raise_for_status = MagicMock()
        dummy_response.json = MagicMock(return_value="mango_response")
        mock_requests.return_value = dummy_response
        trader._create_jwt_token = MagicMock(return_value="mango_token")
        trader._create_market_price_order_query = MagicMock(return_value="mango_query")

        response = trader._send_order("mango", True, volume=0.55)
        self.assertEqual(response, None)

        response = trader._send_order("mango", False, price=500)
        self.assertEqual(response, None)

        response = trader._send_order("mango", True)
        self.assertEqual(response, None)
        trader._create_market_price_order_query.assert_not_called()

    def test__create_limit_order_query_return_correct_query(self):
        expected_query = {
            "market": "mango",
            "side": "bid",
            "volume": "0.76",
            "price": "500",
            "ord_type": "limit",
        }
        expected_query = urlencode(expected_query).encode()
        trader = UpbitTrader()

        query = trader._create_limit_order_query("mango", True, 500, 0.76)

        self.assertEqual(query, expected_query)

    def test__create_market_price_order_query_query_return_correct_query(self):
        expected_buy_query = {
            "market": "mango",
            "side": "bid",
            "price": "500",
            "ord_type": "price",
        }
        expected_buy_query = urlencode(expected_buy_query).encode()
        expected_sell_query = {
            "market": "mango",
            "side": "ask",
            "volume": "0.76",
            "ord_type": "market",
        }
        expected_sell_query = urlencode(expected_sell_query).encode()

        trader = UpbitTrader()

        query = trader._create_market_price_order_query("mango", price=500)

        self.assertEqual(query, expected_buy_query)

        query = trader._create_market_price_order_query("mango", volume=0.76)

        self.assertEqual(query, expected_sell_query)

        query = trader._create_market_price_order_query("mango", 500, 0.76)

        self.assertEqual(query, None)

    @patch("requests.get")
    def test__query_order_list_should_send_correct_request(self, mock_requests):
        query_states = ["done", "wait", "cancel"]
        states_query_string = "&".join(["states[]={}".format(state) for state in query_states])
        expected_query_string = states_query_string.encode()

        class DummyResponse:
            pass

        dummy_response = DummyResponse()
        dummy_response.raise_for_status = MagicMock()
        dummy_response.json = MagicMock(return_value="mango_response")
        mock_requests.return_value = dummy_response
        trader = UpbitTrader()
        trader._create_jwt_token = MagicMock(return_value="mango_token")

        response = trader._query_order_list()

        self.assertEqual(response, "mango_response")
        dummy_response.raise_for_status.assert_called_once()
        dummy_response.json.assert_called_once()
        trader._create_jwt_token.assert_called_once_with(
            trader.ACCESS_KEY, trader.SECRET_KEY, expected_query_string
        )
        mock_requests.assert_called_once_with(
            trader.SERVER_URL + "/v1/orders",
            params=expected_query_string,
            headers={"Authorization": "Bearer mango_token"},
        )

    @patch("requests.get")
    def test__query_account_should_send_correct_request(self, mock_requests):
        class DummyResponse:
            pass

        dummy_response = DummyResponse()
        dummy_response.raise_for_status = MagicMock()
        dummy_response.json = MagicMock(return_value="mango_response")
        mock_requests.return_value = dummy_response
        trader = UpbitTrader()
        trader._create_jwt_token = MagicMock(return_value="mango_token")

        response = trader._query_account()

        self.assertEqual(response, "mango_response")
        dummy_response.raise_for_status.assert_called_once()
        dummy_response.json.assert_called_once()
        trader._create_jwt_token.assert_called_once_with(trader.ACCESS_KEY, trader.SECRET_KEY)
        mock_requests.assert_called_once_with(
            trader.SERVER_URL + "/v1/accounts",
            headers={"Authorization": "Bearer mango_token"},
        )

    @patch("uuid.uuid4")
    @patch("jwt.encode")
    @patch("hashlib.sha512")
    def test__create_jwt_token_should_return_correct_token(self, mock_hash, mock_jwt, mock_uuid):
        trader = UpbitTrader()
        mock_m = MagicMock()
        mock_hash.return_value = mock_m
        mock_uuid.return_value = "uuid_mango"
        mock_m.hexdigest.return_value = "hash_mango"
        trader._create_jwt_token("ak", "sk", "mango_query")

        mock_hash.assert_called_once()
        mock_m.update.assert_called_once_with("mango_query")
        mock_m.hexdigest.assert_called_once()
        mock_jwt.assert_called_once_with(
            {
                "access_key": "ak",
                "nonce": "uuid_mango",
                "query_hash": "hash_mango",
                "query_hash_alg": "SHA512",
            },
            "sk",
        )

    @patch("uuid.uuid4")
    @patch("jwt.encode")
    @patch("hashlib.sha512")
    def test__create_jwt_token_should_return_correct_token_without_payload(
        self, mock_hash, mock_jwt, mock_uuid
    ):
        trader = UpbitTrader()
        mock_uuid.return_value = "uuid_mango"
        trader._create_jwt_token("ak", "sk")

        mock_jwt.assert_called_once_with({"access_key": "ak", "nonce": "uuid_mango"}, "sk")

    @patch("requests.get")
    def test__request_get_should_send_http_request_correctly(self, mock_get):
        trader = UpbitTrader()
        expected_url = "get/apple"
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value="apple_result")
        mock_get.return_value = mock_response
        dummy_headers = "apple_headers"

        self.assertEqual(trader._request_get("get/apple", headers=dummy_headers), "apple_result")
        mock_response.raise_for_status.assert_called_once()
        mock_get.assert_called_once_with(expected_url, headers=dummy_headers)

    @patch("requests.get")
    def test__request_get_return_None_when_invalid_data_received_from_server(self, mock_get):
        def raise_exception():
            raise ValueError("RequestException dummy exception")

        class DummyResponse:
            pass

        mock_response = DummyResponse()
        mock_response.raise_for_status = raise_exception
        mock_response.json = MagicMock(return_value="apple_result")
        mock_get.return_value = mock_response
        dummy_headers = "apple_headers"

        trader = UpbitTrader()
        expected_url = "get/apple"

        self.assertEqual(trader._request_get("get/apple", headers=dummy_headers), None)
        mock_get.assert_called_once_with(expected_url, headers=dummy_headers)