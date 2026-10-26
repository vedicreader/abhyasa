# Abhyasa.app: a SwiftUI window on the abhyasa server. Adapted from Sanketa's Makefile.
# the folder of this Makefile, for the mk/ files
override MK_DIR := $(dir $(lastword $(MAKEFILE_LIST)))mk/
SIGN_ID ?= Apple Development
RELEASE_ID ?= Developer ID Application
APP := build/Abhyasa.app
ENTITLEMENTS := entitlements.plist
# the same zip with a name that does not change, so releases/latest/download/Abhyasa.zip always works
STABLE_ZIP := dist/Abhyasa.zip

.PHONY: test build lock bundle app release zip publish run install cask verify gatekeeper

# Values from the command line go to recipes only through the environment ("$$FILTER"), so the shell never parses
# them. Each value must also pass this check, which reads the raw text with $(value) and so never expands it.
override SAFE_CHARS := a b c d e f g h i j k l m n o p q r s t u v w x y z A B C D E F G H I J K L M N O P Q R S T U V W X Y Z \
	0 1 2 3 4 5 6 7 8 9 _ . / -
override empty :=
override space := $(empty) $(empty)
override tab := $(empty)	$(empty)
override define newline


endef
override strip_chars = $(if $2,$(call strip_chars,$(subst $(firstword $2),,$1),$(wordlist 2,$(words $2),$2)),$1)
override blanks_marked = $(subst $(space),!,$(subst $(tab),!,$(subst $(newline),!,$1)))
override check_var = $(if $(call strip_chars,$(call blanks_marked,$(value $1)),$2),$(error $1 has a character that is not safe. Use only letters, digits and _ . / -))
# a value that starts with - would be read as an option
override check_dash = $(if $(filter -%,$(value $1)),$(error $1 must not start with -))
# identity names such as "Apple Development: Name (TEAM)": spaces are safe in them, tabs and new lines are not
override check_identity = $(if $(call strip_chars,$(subst $(space),,$(subst $(tab),!,$(subst $(newline),!,$(value $1)))),$(SAFE_CHARS) ( ) :),$(error $1 has a character that is not safe. Use only letters, digits, spaces and _ . / - ( ) :))

# VERSION is checked before the ZIP default below expands it
VERSION := $(shell /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' Resources/Info.plist)
$(call check_var,VERSION,$(SAFE_CHARS))$(call check_dash,VERSION)
# defaults as plain text (:=), so the check below sees no $( ) in them
ifeq ($(origin INSTALL_DIR),undefined)
INSTALL_DIR := $(HOME)/Applications
endif
ifeq ($(origin ZIP),undefined)
ZIP := dist/Abhyasa-$(VERSION).zip
endif
# the uv for make lock; the app does not bundle uv, it uses the uv that the cask installs (depends_on formula: "uv")
ifeq ($(origin UV),undefined)
UV := /opt/homebrew/bin/uv
endif
NOTES := dist/notes-$(VERSION).md
TAP ?= ../../homebrew-tap
$(foreach v,FILTER INSTALL_DIR ZIP APP STABLE_ZIP NOTES TAP UV,$(call check_var,$v,$(SAFE_CHARS))$(call check_dash,$v))
$(foreach v,SIGN_ID RELEASE_ID,$(call check_identity,$v))
export FILTER INSTALL_DIR ZIP SIGN_ID RELEASE_ID TAP UV

# release and publish notarize and upload, so they refuse make -n, make -i and their other forms
include $(MK_DIR)no-dry-run.mk

# FILTER=<name> runs only the tests whose names match (letters, digits and _ . / - only)
test:
	swift test $(if $(value FILTER),--filter "$$FILTER")

build:
	swift build

# locks the pinned project again after a change to the abhyasa pin in Resources/Pin/pyproject.toml
lock:
	"$$UV" lock --project Resources/Pin

# swift build in release mode; no Metal shaders here, so xcodebuild is not necessary
bundle:
	swift build -c release --arch arm64
	mkdir -p $(APP)/Contents/MacOS $(APP)/Contents/Resources /tmp/abhyasa-trash
	# a fresh inode: overwriting an executable in place can get it killed at exec on its cached signature
	if [ -e $(APP)/Contents/MacOS/Abhyasa ]; then mv $(APP)/Contents/MacOS/Abhyasa /tmp/abhyasa-trash/Abhyasa-$$$$; fi
	cp "$$(swift build -c release --arch arm64 --show-bin-path)/Abhyasa" $(APP)/Contents/MacOS/Abhyasa
	cp Resources/Info.plist $(APP)/Contents/Info.plist
	# old folders move aside, so no stale file breaks the sealed-resource signature
	if [ -e $(APP)/Contents/Resources/Pin ]; then mv $(APP)/Contents/Resources/Pin /tmp/abhyasa-trash/Pin-$$$$; fi
	cp -R Resources/Pin $(APP)/Contents/Resources/Pin
	if [ -f Resources/AppIcon.icns ]; then cp Resources/AppIcon.icns $(APP)/Contents/Resources/; fi

# SIGN_ID=- gives an ad-hoc signature, for CI only
app: bundle
	codesign --force --options runtime --timestamp=none --entitlements $(ENTITLEMENTS) --sign "$$SIGN_ID" $(APP)

# release (notarized, stapled and checked) and publish (GitHub release), with ZIP_APP
include $(MK_DIR)release.mk

zip:
	$(ZIP_APP)

# opens the app: it shows a window, so run it only when you want to use it
run:
	open $(APP)

# move the old bundle aside, then copy a fresh one: cp -R over a signed bundle overwrites the executable in place
install:
	mkdir -p "$$INSTALL_DIR" /tmp/abhyasa-trash
	if [ -e "$$INSTALL_DIR/Abhyasa.app" ]; then mv "$$INSTALL_DIR/Abhyasa.app" /tmp/abhyasa-trash/Abhyasa.app-$$$$; fi
	ditto $(APP) "$$INSTALL_DIR/Abhyasa.app"

# writes this version and the hash of its release zip into the Homebrew cask in $TAP; it does not commit or push.
# The first time, it copies cask/abhyasa.rb (with depends_on formula: "uv") into the tap.
cask:
	test -f "dist/Abhyasa-$(VERSION).zip"
	test -d "$$TAP/Casks"
	if [ ! -e "$$TAP/Casks/abhyasa.rb" ]; then cp cask/abhyasa.rb "$$TAP/Casks/abhyasa.rb"; fi
	sum=$$(shasum -a 256 "dist/Abhyasa-$(VERSION).zip" | cut -d ' ' -f 1) && \
	sed -i '' -e 's/^  version ".*"/  version "$(VERSION)"/' -e "s/^  sha256 \".*\"/  sha256 \"$$sum\"/" "$$TAP/Casks/abhyasa.rb"
	grep -E '^  (version|sha256) ' "$$TAP/Casks/abhyasa.rb"

# checks the bundle without opening it
verify:
	@python3 -c "import plistlib,sys,os; a=sys.argv[1]; p=plistlib.load(open(a+'/Contents/Info.plist','rb')); assert p['CFBundleIdentifier']=='dev.vedicreader.abhyasa'; assert p['CFBundleURLTypes'][0]['CFBundleURLSchemes']==['abhyasa']; assert p['NSMicrophoneUsageDescription']; os.access(a+'/Contents/MacOS/Abhyasa',os.X_OK) or sys.exit('no Abhyasa'); os.path.exists(a+'/Contents/MacOS/uv') and sys.exit('uv must not be in the bundle'); [os.path.isfile(a+'/Contents/Resources/Pin/'+f) or sys.exit('no '+f) for f in ('pyproject.toml','uv.lock')]; print('bundle ok')" $(APP)
	@grep -q 'depends_on formula: "uv"' cask/abhyasa.rb || { echo "cask/abhyasa.rb does not depend on uv"; exit 1; }
	codesign --verify --deep --strict $(APP)
	@codesign -d --entitlements - $(APP) 2>/dev/null | grep -q audio-input || { echo "no audio-input entitlement"; exit 1; }
	@codesign -dvv $(APP) 2>&1 | grep Authority
	@du -sh $(APP)

# Gatekeeper's view: accepted only after notarization
gatekeeper:
	spctl -a -t exec -vv $(APP)
