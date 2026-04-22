import {
  CheckIcon,
  CloseButton,
  Combobox,
  Group,
  Pill,
  PillsInput,
  useCombobox,
} from "@mantine/core";
import { useState } from "react";

interface Props {
  data: string[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  label?: string;
  width?: number | string;
}

/**
 * Multi-select with pills inside the input + search. Built explicitly on
 * Mantine's Combobox primitives rather than the composite `<MultiSelect>`
 * so selection, re-opening, and typing stay in our control.
 */
export function MultiPillSelect({
  data,
  value,
  onChange,
  placeholder,
  label,
  width = 260,
}: Props) {
  const combobox = useCombobox({
    onDropdownClose: () => combobox.resetSelectedOption(),
    onDropdownOpen: () => combobox.updateSelectedOptionIndex("active"),
  });
  const [search, setSearch] = useState("");

  const toggle = (val: string) =>
    onChange(value.includes(val) ? value.filter((v) => v !== val) : [...value, val]);
  const remove = (val: string) => onChange(value.filter((v) => v !== val));

  const pills = value.map((item) => (
    <Pill key={item} withRemoveButton onRemove={() => remove(item)}>
      {item}
    </Pill>
  ));

  const options = data
    .filter((item) => item.toLowerCase().includes(search.toLowerCase().trim()))
    .map((item) => {
      const selected = value.includes(item);
      return (
        <Combobox.Option value={item} key={item} active={selected}>
          <Group gap="xs" wrap="nowrap">
            {selected && <CheckIcon size={12} />}
            <span>{item}</span>
          </Group>
        </Combobox.Option>
      );
    });

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={(v) => {
        toggle(v);
        // Clear the search filter so the full list is available for the
        // next pick, and re-open the dropdown (Combobox closes by default).
        setSearch("");
        combobox.openDropdown();
      }}
      withinPortal
      shadow="md"
    >
      <Combobox.DropdownTarget>
        <PillsInput
          label={label}
          w={width}
          mah={36}
          style={{ overflow: "hidden" }}
          onClick={() => combobox.openDropdown()}
          rightSection={
            value.length > 0 ? (
              <CloseButton
                aria-label="Clear"
                size="sm"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onChange([])}
              />
            ) : null
          }
        >
          <Pill.Group
            style={{
              flexWrap: "nowrap",
              overflowX: "auto",
              minWidth: 0,
              scrollbarWidth: "none",
            }}
          >
            {pills}
            <Combobox.EventsTarget>
              <PillsInput.Field
                onFocus={() => combobox.openDropdown()}
                onBlur={() => combobox.closeDropdown()}
                value={search}
                placeholder={value.length === 0 ? placeholder : ""}
                onChange={(e) => {
                  combobox.updateSelectedOptionIndex();
                  setSearch(e.currentTarget.value);
                  combobox.openDropdown();
                }}
                onKeyDown={(e) => {
                  if (e.key === "Backspace" && search.length === 0 && value.length > 0) {
                    e.preventDefault();
                    remove(value[value.length - 1]);
                  }
                }}
              />
            </Combobox.EventsTarget>
          </Pill.Group>
        </PillsInput>
      </Combobox.DropdownTarget>
      <Combobox.Dropdown>
        <Combobox.Options mah={240} style={{ overflowY: "auto" }}>
          {options.length > 0 ? (
            options
          ) : (
            <Combobox.Empty>Nothing Found</Combobox.Empty>
          )}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}
