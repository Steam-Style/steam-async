import pytest

from steam.client import SteamClient


@pytest.mark.asyncio
class TestSteamClient:
    async def test_get_product_info(self):
        client = SteamClient()

        try:
            await client.connect(retry=True)
            assert client.connected

            await client.anonymous_login()
            assert client.logged_in

            product_info = await client.get_product_info(app_ids=[440], package_ids=[1])
            assert product_info is not None

            if product_info:
                assert 440 in product_info["apps"]
                assert "common" in product_info["apps"][440]
                assert product_info["apps"][440]["common"]["name"] == "Team Fortress 2"

                assert 1 in product_info["packages"]
                assert product_info["packages"][1]["packageid"] == 1

        except Exception as e:
            pytest.fail(f"Integration test failed: {e}")
        finally:
            await client.disconnect()

    async def test_get_access_tokens(self):
        client = SteamClient()

        try:
            await client.connect(retry=True)
            assert client.connected

            await client.anonymous_login()
            assert client.logged_in

            access_tokens = await client.get_access_tokens(app_ids=[440], package_ids=[1])
            assert access_tokens is not None

            if access_tokens:
                assert 440 in access_tokens["apps"]
                assert isinstance(access_tokens["apps"][440], int)

                assert 1 in access_tokens["packages"]
                assert isinstance(access_tokens["packages"][1], int)

        except Exception as e:
            pytest.fail(f"Integration test failed: {e}")
        finally:
            await client.disconnect()
