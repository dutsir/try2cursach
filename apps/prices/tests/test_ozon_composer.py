from apps.prices.ozon_composer import (
    extract_products_from_composer,
    is_composer_api_url,
    is_valid_ozon_product_name,
    normalize_product_url,
)


def test_is_composer_api_url():
    assert is_composer_api_url(
        'https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=%2Fcategory%2Fnoutbuki'
    )
    assert not is_composer_api_url('https://www.ozon.ru/product/foo-123/')


def test_normalize_product_url():
    assert normalize_product_url('/product/noutbuk-asus-12345678/') == (
        'https://www.ozon.ru/product/noutbuk-asus-12345678/'
    )


def test_reject_promo_names():
    assert not is_valid_ozon_product_name('Распродажа')
    assert not is_valid_ozon_product_name('Цена что надо')
    assert is_valid_ozon_product_name('Ноутбук ASUS VivoBook 15')


def test_extract_from_widget_states():
    payload = {
        'layout': [{'component': 'searchResultsV2', 'stateId': 'st1'}],
        'widgetStates': {
            'st1': (
                '{"items":[{"sku":12345678,'
                '"action":{"link":"/product/noutbuk-asus-12345678/"},'
                '"mainState":{"title":{"text":"Ноутбук ASUS VivoBook 15"}},'
                '"priceV2":{"price":[{"text":"45 990 ₽"}]}}]}'
            ),
        },
    }
    rows = extract_products_from_composer(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row['vendor_code'] == '12345678'
    assert row['price'] == 45990
    assert 'ASUS' in row['name']
    assert row['url'].endswith('/product/noutbuk-asus-12345678/')
