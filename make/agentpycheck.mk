TEMPFILE:=$(shell mktemp)
DATADIR:=$(abs_top_builddir)/../tests/data/metadata

check: $(TARGET:%=xml-check.%) $(SYMTARGET:%=xml-check.%) $(TARGET:%=delay-check.%)

xml-check.%: %
	$(eval INPUT=$(subst xml-check.,,$@))
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib python ./$(INPUT) -o metadata > $(TEMPFILE)
	diff $(TEMPFILE) $(DATADIR)/$(INPUT).xml
	rm $(TEMPFILE)

xml-upload.%: %
	$(eval INPUT=$(subst xml-upload.,,$@))
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib python ./$(INPUT) -o metadata > $(DATADIR)/$(INPUT).xml

# If test will fail, rerun fence agents to show problems
delay-check.%: %
	$(eval INPUT=$(subst delay-check.,,$@))
	test `PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib /usr/bin/time -f "%e" \
	python ./$(INPUT) --delay 10 $(FENCE_TEST_ARGS) -- 2>&1 |\
	sed 's/\.//' | tail -n 1` -ge 1000 || \
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib /usr/bin/time -f "%e" \
	python ./$(INPUT) --delay 0 $(FENCE_TEST_ARGS) --
