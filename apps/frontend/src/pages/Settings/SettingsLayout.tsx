import { Group, NavLink, Stack, Title } from "@mantine/core";
import { Outlet, useLocation, useNavigate } from "react-router";

const ITEMS = [
  { label: "Device Settings", to: "/settings/devices" },
  { label: "Entity Settings", to: "/settings/entities" },
  { label: "Global Policies", to: "/settings/global" },
  { label: "Exceptions", to: "/settings/exceptions" },
];

export function SettingsLayout() {
  const loc = useLocation();
  const navigate = useNavigate();
  return (
    <Group align="flex-start" gap="lg">
      <Stack w={220} gap="xs">
        <Title order={5}>Settings</Title>
        {ITEMS.map((it) => (
          <NavLink
            key={it.to}
            component="a"
            href={it.to}
            label={it.label}
            active={loc.pathname === it.to || loc.pathname.startsWith(`${it.to}/`)}
            onClick={(e) => {
              e.preventDefault();
              navigate(it.to);
            }}
          />
        ))}
      </Stack>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Outlet />
      </div>
    </Group>
  );
}
