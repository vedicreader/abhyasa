# release and publish. The Makefile includes this after it sets APP, VERSION, ZIP, STABLE_ZIP, NOTES and ENTITLEMENTS
# and checks them. Copied from Sanketa's mk/release.mk.

# release and publish use the version in Info.plist, and publish uploads the zip with its standard name
ifneq (,$(filter release publish,$(MAKECMDGOALS)))
ifneq (file,$(origin VERSION))
$(error release and publish use the version in Resources/Info.plist. Do not set VERSION)
endif
endif
ifneq (,$(filter publish,$(MAKECMDGOALS)))
ifneq (file,$(origin ZIP))
$(error publish uses its own zip name. Do not set ZIP)
endif
endif

# the commands; override, so that a value from the command line cannot replace them
override CODESIGN := codesign
override NOTARIZE := scripts/notarize.sh
override STAPLE := xcrun stapler staple
# fails for an app that has no stapled notarization ticket or that Gatekeeper does not accept
override CHECK_NOTARIZED = xcrun stapler validate $(APP) && spctl --assess --type execute -vv $(APP)
override GH := gh

# zips the app to $ZIP; an old zip goes to /tmp/abhyasa-trash, because rm is not allowed here
override ZIP_APP = mkdir -p "$$(dirname "$$ZIP")" /tmp/abhyasa-trash && \
	{ if [ -e "$$ZIP" ]; then mv "$$ZIP" "/tmp/abhyasa-trash/$$(basename "$$ZIP")-$$$$"; fi; } && \
	ditto -c -k --keepParent $(APP) "$$ZIP"

# Developer ID signature with a secure timestamp. Notarized and stapled. Without notary
# credentials release stops; make app and make zip give a local build that is not notarized.
release: bundle
	$(CODESIGN) --force --options runtime --timestamp --entitlements $(ENTITLEMENTS) --sign "$$RELEASE_ID" $(APP)
	$(CODESIGN) --verify --deep --strict --verbose=2 $(APP)
	$(ZIP_APP)
	@$(NOTARIZE) "$$ZIP"; s=$$?; \
	if [ $$s -eq 3 ]; then echo "release stops: scripts/notarize.sh found no notary credentials, so $$ZIP is not notarized. Write ~/.config/abhyasa/notary.json (or Sanketa's ~/.config/sanketa/notary.json) with key_id, issuer_id and key_path, or run 'xcrun notarytool store-credentials abhyasa-notary --apple-id <id> --team-id 7632NRC559' and then 'make release NOTARY_PROFILE=abhyasa-notary'." >&2; fi; \
	exit $$s
	$(STAPLE) $(APP)
	$(CHECK_NOTARIZED)
	$(ZIP_APP)

# makes the GitHub release mac-v$(VERSION) on main with the notarized zip, and the same zip as Abhyasa.zip for the
# download link. The tag has a mac- prefix, so it does not clash with the v tags of the Python package.
publish: release
	$(CHECK_NOTARIZED)
	printf '%s\n\n%s\n\n%s\n\n%s\n' "Abhyasa $(VERSION) for macOS 26 on Apple Silicon. The app has a Developer ID signature, and Apple notarized it." \
		"To install it, unzip the file and move Abhyasa.app to Applications. Or run: brew install --cask vedicreader/tap/abhyasa" \
		"Abhyasa-$(VERSION).zip and Abhyasa.zip are the same file. Abhyasa.zip has a name that does not change, so the download link always gets the latest release." \
		"The app needs uv (brew install uv; the cask installs it). On the first launch, uv downloads Python and the abhyasa packages one time. The tutor model can use the network." > $(NOTES)
	mkdir -p /tmp/abhyasa-trash
	if [ -e $(STABLE_ZIP) ]; then mv $(STABLE_ZIP) /tmp/abhyasa-trash/Abhyasa.zip-$$$$; fi
	cp "$$ZIP" $(STABLE_ZIP)
	$(GH) release create mac-v$(VERSION) "$$ZIP" $(STABLE_ZIP) --target main --title "Abhyasa $(VERSION) for Mac" --notes-file $(NOTES)
