# climabar.mod: standalone build with a stock riscv64 cross toolchain (Fedora gcc-riscv64-linux-gnu).
# The SDK is only used for its linker scripts; modules are linked as ELF64 and stored as ELF32,
# like the SDK's scripts/Makefile.mods does.
SDK    ?= ../sdk/d1s-melis
CROSS  ?= riscv64-linux-gnu-
CC      = $(CROSS)gcc
LD      = $(CROSS)ld
OBJCOPY = $(CROSS)objcopy

# -fshort-enums: the firmware was built with one-byte enums (display layer layout depends on it)
CFLAGS  = -march=rv64gc -mabi=lp64d -mcmodel=medany -msmall-data-limit=0 -O2 -Wall -Wextra -std=gnu11 \
          -ffreestanding -fno-builtin -fno-tree-loop-distribute-patterns -fno-pic -fno-common \
          -fshort-enums -ffunction-sections -fdata-sections
LDFLAGS = -N --gc-sections -L $(SDK)/scripts -T lds/climabar.lds -Map=build/climabar.map

OBJS = build/start.o build/climabar.o

all: build/climabar.mod

build/%.o: src/%.c src/melis.h build/assets.h | build
	$(CC) $(CFLAGS) -Ibuild -c $< -o $@
build/%.o: src/%.S | build
	$(CC) $(CFLAGS) -c $< -o $@
build/climabar.elf: $(OBJS) lds/climabar.lds
	$(LD) $(LDFLAGS) $(OBJS) -o $@
build/climabar.mod: build/climabar.elf
	$(OBJCOPY) -S -O elf32-littleriscv -R .note -R .comment -R .riscv.attributes -R .got -R .got.plt $< $@
build/assets.h: tools/gen_assets.py layout.json $(wildcard assets/*.png) | build
	python3 tools/gen_assets.py assets layout.json $@
build:
	mkdir -p build

# regenerate the icons from Material Symbols (downloaded once into icons_src/), with AUTO / SYNC labels
icons:
	python3 tools/fetch_icons.py assets icons_src

# all images: the icons above, plus the car / doors / seat belt redrawn from the stock trip computer screen
# (FW = the unpacked stock rootfs, firmware/8369HD_unpacked/data_udisk.fex.out)
FW ?= ../firmware/8369HD_unpacked/data_udisk.fex.out
assets: icons
	python3 tools/import_vehicle_assets.py $(FW)/apps/Data/CarComputer.data assets

# the minimal test module (docs/safety.md): same name, type and load address as climabar.mod, no display work.
# THREAD=1: also creates and names its thread like climabar.mod, then sleeps. Output: build/minimal.mod - install it
# as mod/climabar.mod in an image before trying new module code on the head unit.
THREAD ?= 0
minimal: | build
	$(CC) $(CFLAGS) -DMINIMAL -c src/start.S -o build/minimal_start.o
	$(CC) $(CFLAGS) -DTHREAD=$(THREAD) -Isrc -c test_minimal/minimal.c -o build/minimal.o
	$(LD) -N --gc-sections -L $(SDK)/scripts -T lds/minimal.lds build/minimal.o build/minimal_start.o -o build/minimal.elf
	$(OBJCOPY) -S -O elf32-littleriscv -R .note -R .comment -R .riscv.attributes -R .got -R .got.plt build/minimal.elf build/minimal.mod

clean:
	rm -rf build

.PHONY: all icons assets minimal clean
