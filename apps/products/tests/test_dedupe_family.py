from __future__ import annotations

from apps.products.dedupe.family import (
    compute_family_key,
    compute_variant_key,
    derive_family_name,
    extract_ram_model_code,
    extract_ssd_model_code,
    make_family_signature,
    split_specs,
)


class TestSplitSpecs:
    def test_ssd_storage_goes_to_variant(self) -> None:
        specs = {'storage_gb': 1000, 'interface': 'NVMe', 'form_factor': 'M.2 2280'}
        common, variant = split_specs(specs, 'ssd-nakopiteli')
        assert variant == {'storage_gb': 1000}
        assert common == {'interface': 'NVMe', 'form_factor': 'M.2 2280'}

    def test_ram_kit_goes_to_variant(self) -> None:
        specs = {'ram_gb': 16, 'modules_count': 2, 'frequency_mhz': 3200, 'type': 'DDR4'}
        common, variant = split_specs(specs, 'operativnaya-pamyat')
        assert variant == {'ram_gb': 16, 'modules_count': 2}
        assert common == {'frequency_mhz': 3200, 'type': 'DDR4'}

    def test_unknown_category_has_no_variants(self) -> None:
        specs = {'storage_gb': 1000, 'whatever': 'x'}
        common, variant = split_specs(specs, 'processory')
        assert variant == {}
        assert common == {'storage_gb': 1000, 'whatever': 'x'}

    def test_empty_and_none_values_dropped(self) -> None:
        common, variant = split_specs({'storage_gb': 1000, 'color': '', 'extra': None}, 'ssd-nakopiteli')
        assert variant == {'storage_gb': 1000}
        assert common == {}

    def test_none_specs_returns_empty(self) -> None:
        common, variant = split_specs(None, 'ssd-nakopiteli')
        assert common == {} and variant == {}


class TestComputeFamilyKey:
    def test_deterministic_independent_of_specs_order(self) -> None:
        a = compute_family_key(
            brand='Samsung', model_code='980 PRO',
            common_specs={'interface': 'NVMe', 'form_factor': 'M.2 2280'},
        )
        b = compute_family_key(
            brand='Samsung', model_code='980 PRO',
            common_specs={'form_factor': 'M.2 2280', 'interface': 'NVMe'},
        )
        assert a == b

    def test_case_insensitive_brand_and_model(self) -> None:
        assert (
            compute_family_key(brand='SAMSUNG', model_code='980 pro')
            == compute_family_key(brand='samsung', model_code='980 PRO')
        )

    def test_generation_and_year_change_key(self) -> None:
        a = compute_family_key(brand='Intel', model_code='i5-13400')
        b = compute_family_key(brand='Intel', model_code='i5-13400', generation='F')
        c = compute_family_key(brand='Intel', model_code='i5-13400', year=2023)
        assert a != b != c != a


class TestComputeVariantKey:
    def test_same_specs_same_key(self) -> None:
        assert (
            compute_variant_key({'storage_gb': 1000})
            == compute_variant_key({'storage_gb': 1000})
        )

    def test_empty_variant_stable(self) -> None:
        assert compute_variant_key({}) == compute_variant_key(None)

    def test_different_storage_different_key(self) -> None:
        assert compute_variant_key({'storage_gb': 500}) != compute_variant_key({'storage_gb': 1000})


class TestDeriveFamilyName:
    def test_strips_storage_suffix(self) -> None:
        assert (
            derive_family_name('Накопитель SSD Samsung 980 PRO 1TB MZ-V8P1T0BW')
            == 'Накопитель SSD Samsung 980 PRO MZ-V8P1T0BW'
        )

    def test_strips_ram_capacity(self) -> None:
        assert (
            derive_family_name('Оперативная память Kingston Fury Beast 32GB DDR4 3200')
            == 'Оперативная память Kingston Fury Beast DDR4 3200'
        )

    def test_strips_kit_notation(self) -> None:
        assert (
            derive_family_name('Kingston Fury 2x16ГБ DDR5')
            == 'Kingston Fury DDR5'
        )

    def test_strips_russian_units(self) -> None:
        assert derive_family_name('Crucial P3 500 ГБ') == 'Crucial P3'

    def test_does_not_break_when_nothing_to_strip(self) -> None:
        assert derive_family_name('Intel Core i5-13400F') == 'Intel Core i5-13400F'

    def test_empty_input(self) -> None:
        assert derive_family_name('') == ''


class TestExtractSsdModelCode:
    def test_kingspec_variants_collapse(self) -> None:
        a = extract_ssd_model_code(
            '2048 ГБ 2.5" SATA накопитель KingSpec P3-2TB [SATA, чтение - 580]'
        )
        b = extract_ssd_model_code(
            '1024 ГБ 2.5" SATA накопитель KingSpec P3-1TB [SATA, чтение - 570]'
        )
        assert a and b and a == b, (a, b)
        assert 'kingspec p3' in a

    def test_samsung_980_pro(self) -> None:
        a = extract_ssd_model_code('1024 ГБ SSD M.2 2280 Samsung 980 PRO MZ-V8P1T0BW')
        b = extract_ssd_model_code('512 ГБ SSD M.2 2280 Samsung 980 PRO MZ-V8P500BW')
        assert 'samsung' in a and '980 pro' in a
        # MPN-токены отличаются ёмкостью, но они выкидываются как длинные
        # альфа+цифровые — варианты схлопываются в одну семью.
        assert a == b, (a, b)
        assert 'mz-' not in a

    def test_wd_blue_sn570(self) -> None:
        code = extract_ssd_model_code('500 ГБ SSD M.2 2280 WD Blue SN570 WDS500G3B0C')
        assert 'wd blue sn570' in code

    def test_crucial_p3(self) -> None:
        code = extract_ssd_model_code('1000 ГБ SSD M.2 2280 Crucial P3 CT1000P3SSD8')
        assert 'crucial p3' in code

    def test_empty_input(self) -> None:
        assert extract_ssd_model_code('') == ''

    def test_brand_prepended_if_missing(self) -> None:
        code = extract_ssd_model_code('SN570 500GB', brand='WD')
        assert code.startswith('wd')

    def test_returns_empty_when_only_noise(self) -> None:
        # Только шумовые токены — не сможем выделить модель
        code = extract_ssd_model_code('1 ТБ SSD SATA')
        assert code == ''


class TestMakeFamilySignature:
    def test_ssd_returns_signature(self) -> None:
        sig = make_family_signature(
            name='2048 ГБ 2.5" SATA накопитель KingSpec P3-2TB [SATA, чтение - 580]',
            brand='', vendor_code='', specs={'storage_gb': 2048},
            category_slug='ssd-nakopiteli',
        )
        assert sig is not None
        assert 'kingspec p3' in sig['model_code']
        assert sig['variant_specs'] == {'storage_gb': 2048}
        assert sig['common_specs'] == {}
        assert len(sig['family_key']) == 40
        assert len(sig['variant_key']) == 40

    def test_two_ssd_variants_share_family_key(self) -> None:
        a = make_family_signature(
            name='250 ГБ 2.5" SATA накопитель Samsung 870 EVO MZ-77E250BW',
            brand='samsung', vendor_code='MZ-77E250BW', specs={'storage_gb': 250},
            category_slug='ssd-nakopiteli',
        )
        b = make_family_signature(
            name='500 ГБ 2.5" SATA накопитель Samsung 870 EVO MZ-77E500BW',
            brand='samsung', vendor_code='MZ-77E500BW', specs={'storage_gb': 500},
            category_slug='ssd-nakopiteli',
        )
        assert a and b
        assert a['family_key'] == b['family_key']
        assert a['variant_key'] != b['variant_key']

    def test_cpu_category_returns_none(self) -> None:
        sig = make_family_signature(
            name='Процессор Intel Core i5-13400F BOX',
            brand='intel', vendor_code='', specs={'cpu_family': 'core i5'},
            category_slug='processory',
        )
        assert sig is None

    def test_ssd_without_recognized_model_returns_none(self) -> None:
        sig = make_family_signature(
            name='1 ТБ SSD SATA',
            brand='', vendor_code='', specs={},
            category_slug='ssd-nakopiteli',
        )
        assert sig is None

    def test_laptop_two_configs_share_family(self) -> None:
        a = make_family_signature(
            name='Ноутбук ASUS Vivobook 17 X1704VA-AU982, 17.3", IPS, Intel Core 5 120U, 16ГБ DDR5, 512ГБ SSD,  синий',
            brand='intel',  # wrong brand from parser
            vendor_code='90NB13X2-M00ML0',
            specs={'ram_gb': 16, 'storage_gb': 512, 'screen_in': '17.3'},
            category_slug='noutbuki',
        )
        b = make_family_signature(
            name='Ноутбук ASUS Vivobook 17 X1704VA-AU985, 17.3", IPS, Intel Core 5 120U, 8ГБ DDR5, 256ГБ SSD,  синий',
            brand='nvidia',  # wrong brand from parser
            vendor_code='90NB13X2-M00ML5',
            specs={'ram_gb': 8, 'storage_gb': 256, 'screen_in': '17.3'},
            category_slug='noutbuki',
        )
        assert a and b
        assert 'asus vivobook 17' in a['model_code']
        # Конфигурационные суффиксы (-AU982 / -AU985) и MPN — это длинные
        # альфа-цифровые токены, оба выкидываются. Семья одна.
        assert a['family_key'] == b['family_key']
        assert a['variant_specs'] == {'ram_gb': 16, 'storage_gb': 512}
        assert b['variant_specs'] == {'ram_gb': 8, 'storage_gb': 256}
        assert a['variant_key'] != b['variant_key']

    def test_pc_garbage_returns_none(self) -> None:
        # «600 баллов за отзыв» — мусор без префикса «ПК», экстрактор не
        # вытаскивает модель → семья не создаётся.
        sig = make_family_signature(
            name='600 баллов за отзыв',
            brand='', vendor_code='', specs={},
            category_slug='sobrannyepk',
        )
        assert sig is None

    def test_pc_model_extracted(self) -> None:
        sig = make_family_signature(
            name='ПК Lenovo Legion T5 26IOB6 [90RT00UNRS] [Intel Core i5-11400F, 16 ГБ DDR4, GeForce RTX 3070]',
            brand='lenovo', vendor_code='90RT00UNRS',
            specs={'ram_gb': 16, 'storage_gb': 1000, 'cpu_family': 'core i5'},
            category_slug='sobrannyepk',
        )
        assert sig is not None
        assert 'lenovo legion' in sig['model_code']
        # cpu_family остаётся в common — не variant
        assert 'cpu_family' in sig['common_specs']
        assert sig['variant_specs'] == {'ram_gb': 16, 'storage_gb': 1000}

    def test_external_ssd_collapses(self) -> None:
        a = make_family_signature(
            name='4ТБ Внешний диск SSD A-Data SE920, USB-C 4.0, чёрный',
            brand='', vendor_code='SE920-4TCBK',
            specs={'storage_gb': 4096}, category_slug='vneshnie-ssd',
        )
        b = make_family_signature(
            name='1ТБ Внешний диск SSD A-Data SE920, USB-C 4.0, чёрный',
            brand='', vendor_code='SE920-1TCBK',
            specs={'storage_gb': 1024}, category_slug='vneshnie-ssd',
        )
        assert a and b
        assert a['family_key'] == b['family_key']
        assert a['variant_specs'] == {'storage_gb': 4096}
        assert b['variant_specs'] == {'storage_gb': 1024}

    def test_monoblock_two_configs_share_family(self) -> None:
        a = make_family_signature(
            name='23.8" Моноблок MSI Pro AP242P 14M-670XRU Full HD, Intel Core i3 14100, 8ГБ DDR5, 512ГБ SSD,  без ОС черный',
            brand='intel', vendor_code='9S6-AE0621-827',
            specs={'ram_gb': 8, 'storage_gb': 512}, category_slug='monobloki',
        )
        b = make_family_signature(
            name='23.8" Моноблок MSI Pro AP242P 14M-671XRU Full HD, Intel Core i3 14100, 16ГБ DDR5, 1ТБ SSD,  Windows 11 черный',
            brand='intel', vendor_code='9S6-AE0621-828',
            specs={'ram_gb': 16, 'storage_gb': 1024}, category_slug='monobloki',
        )
        assert a and b
        # Суффиксы -670XRU/-671XRU выкинутся как MPN-like (начинаются с цифры).
        # Стоп — они начинаются с буквы. Проверим что 14M-670XRU отсеивается.
        # 14M-670XRU split по '-' → '14M' (длина 3, < 5 → keep, не MPN).
        # Это «14M» — поколение/ревизия модели Pro AP242P. Остаётся в model_code.
        assert a['family_key'] == b['family_key'], (a['model_code'], b['model_code'])
        assert 'pro ap242p' in a['model_code']

    def test_ram_ddr_type_separates_families(self) -> None:
        # Kingston FURY Beast Black DDR4 3200 и DDR5 5200 — разные стандарты,
        # не должны сливаться в одну семью.
        ddr4 = make_family_signature(
            name='Оперативная память Kingston FURY Beast Black [KF432C16BB/8WP] 8 ГБ [DDR4, 8 ГБx1 шт, 3200 МГц, 16(CL)-18-18]',
            brand='kingston', vendor_code='KF432C16BB/8WP',
            specs={'ram_gb': 8, 'modules_count': 1, 'color': 'black'},
            category_slug='operativnaya-pamyat',
        )
        ddr5 = make_family_signature(
            name='Оперативная память Kingston FURY Beast Black [KF552C40BBK2-16] 16 ГБ [DDR5, 8 ГБx2 шт, 5200 МГц, 40(CL)-40-40]',
            brand='kingston', vendor_code='KF552C40BBK2-16',
            specs={'ram_gb': 8, 'modules_count': 2, 'color': 'black'},
            category_slug='operativnaya-pamyat',
        )
        assert ddr4 and ddr5
        assert ddr4['family_key'] != ddr5['family_key'], (ddr4['model_code'], ddr5['model_code'])
        assert 'ddr4' in ddr4['model_code']
        assert '3200' in ddr4['model_code']
        assert 'ddr5' in ddr5['model_code']

    def test_ram_same_series_different_capacity_share_family(self) -> None:
        # Kingston FURY Beast Black DDR4 3200 с 8GB и 16GB — варианты одной семьи.
        a = make_family_signature(
            name='Оперативная память Kingston FURY Beast Black [KF432C16BB/8WP] 8 ГБ [DDR4, 8 ГБx1 шт, 3200 МГц, 16(CL)-18-18]',
            brand='kingston', vendor_code='KF432C16BB/8WP',
            specs={'ram_gb': 8, 'modules_count': 1},
            category_slug='operativnaya-pamyat',
        )
        b = make_family_signature(
            name='Оперативная память Kingston FURY Beast Black [KF432C16BB1/16] 16 ГБ [DDR4, 16 ГБx1 шт, 3200 МГц, 16(CL)-18-18]',
            brand='kingston', vendor_code='KF432C16BB1/16',
            specs={'ram_gb': 16, 'modules_count': 1},
            category_slug='operativnaya-pamyat',
        )
        assert a and b
        assert a['family_key'] == b['family_key']
        assert a['variant_specs'] == {'ram_gb': 8, 'modules_count': 1}
        assert b['variant_specs'] == {'ram_gb': 16, 'modules_count': 1}

    def test_extract_ram_model_code_basic(self) -> None:
        code = extract_ram_model_code(
            'Оперативная память Kingston FURY Beast Black [KF432C16BB/8WP] 8 ГБ [DDR4, 8 ГБx1 шт, 3200 МГц]',
        )
        assert 'kingston' in code
        assert 'fury' in code
        assert 'beast' in code
        assert 'ddr4' in code
        assert '3200' in code

    def test_laptop_different_series_NOT_merged(self) -> None:
        # B3604CMA и B5604CMA — разные модели ASUS ExpertBook, не должны
        # сливаться в одну семью (это не суффиксы конфига, а полные серии).
        a = make_family_signature(
            name='Ноутбук ASUS ExpertBook B3604CMA-Q90350W, 16", IPS, RAM 8 ГБ',
            brand='', vendor_code='B3604CMA-Q90350W',
            specs={'ram_gb': 8, 'storage_gb': 512}, category_slug='noutbuki',
        )
        b = make_family_signature(
            name='Ноутбук ASUS ExpertBook B5604CMA-QY0235, 16", IPS, RAM 8 ГБ',
            brand='', vendor_code='B5604CMA-QY0235',
            specs={'ram_gb': 8, 'storage_gb': 512}, category_slug='noutbuki',
        )
        assert a and b
        assert a['family_key'] != b['family_key'], (a['model_code'], b['model_code'])
        assert 'b3604cma' in a['model_code']
        assert 'b5604cma' in b['model_code']
