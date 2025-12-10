.PHONY: po mo

po:
	xgettext -Lpython --output=messages.pot makera.py makera.kv
	mkdir -p locales/en/LC_MESSAGES
	mkdir -p locales/zh-CN/LC_MESSAGES
	mkdir -p locales/zh-TW/LC_MESSAGES
	mkdir -p locales/de/LC_MESSAGES
	mkdir -p locales/fr/LC_MESSAGES
	mkdir -p locales/es/LC_MESSAGES
	mkdir -p locales/pt/LC_MESSAGES
	mkdir -p locales/it/LC_MESSAGES
	mkdir -p locales/ja/LC_MESSAGES
	mkdir -p locales/ko/LC_MESSAGES
	touch locales/en/LC_MESSAGES/en.po
	touch locales/zh-CN/LC_MESSAGES/zh-CN.po
	touch locales/zh-TW/LC_MESSAGES/zh-TW.po
	touch locales/de/LC_MESSAGES/de.po
	touch locales/fr/LC_MESSAGES/fr.po
	touch locales/es/LC_MESSAGES/es.po
	touch locales/pt/LC_MESSAGES/pt.po
	touch locales/it/LC_MESSAGES/it.po
	touch locales/ja/LC_MESSAGES/ja.po
	touch locales/ko/LC_MESSAGES/ko.po
	msgmerge --update --no-fuzzy-matching --backup=off locales/en/LC_MESSAGES/en.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/zh-CN/LC_MESSAGES/zh-CN.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/zh-TW/LC_MESSAGES/zh-TW.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/de/LC_MESSAGES/de.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/fr/LC_MESSAGES/fr.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/es/LC_MESSAGES/es.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/pt/LC_MESSAGES/pt.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/it/LC_MESSAGES/it.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/ja/LC_MESSAGES/ja.po messages.pot
	msgmerge --update --no-fuzzy-matching --backup=off locales/ko/LC_MESSAGES/ko.po messages.pot

mo:
	mkdir -p locales/en/LC_MESSAGES
	mkdir -p locales/zh-CN/LC_MESSAGES
	mkdir -p locales/zh-TW/LC_MESSAGES
	mkdir -p locales/de/LC_MESSAGES
	mkdir -p locales/fr/LC_MESSAGES
	mkdir -p locales/es/LC_MESSAGES
	mkdir -p locales/pt/LC_MESSAGES
	mkdir -p locales/it/LC_MESSAGES
	mkdir -p locales/ja/LC_MESSAGES
	mkdir -p locales/ko/LC_MESSAGES
	msgfmt -c -o locales/en/LC_MESSAGES/en.mo locales/en/LC_MESSAGES/en.po
	msgfmt -c -o locales/zh-CN/LC_MESSAGES/zh-CN.mo locales/zh-CN/LC_MESSAGES/zh-CN.po
	msgfmt -c -o locales/zh-TW/LC_MESSAGES/zh-TW.mo locales/zh-TW/LC_MESSAGES/zh-TW.po
	msgfmt -c -o locales/de/LC_MESSAGES/de.mo locales/de/LC_MESSAGES/de.po
	msgfmt -c -o locales/fr/LC_MESSAGES/fr.mo locales/fr/LC_MESSAGES/fr.po
	msgfmt -c -o locales/es/LC_MESSAGES/es.mo locales/es/LC_MESSAGES/es.po
	msgfmt -c -o locales/pt/LC_MESSAGES/pt.mo locales/pt/LC_MESSAGES/pt.po
	msgfmt -c -o locales/it/LC_MESSAGES/it.mo locales/it/LC_MESSAGES/it.po
	msgfmt -c -o locales/ja/LC_MESSAGES/ja.mo locales/ja/LC_MESSAGES/ja.po
	msgfmt -c -o locales/ko/LC_MESSAGES/ko.mo locales/ko/LC_MESSAGES/ko.po