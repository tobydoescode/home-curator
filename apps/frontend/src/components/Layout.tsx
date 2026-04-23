import { AppShell, Group, NavLink, Title } from "@mantine/core";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { LiveIndicator } from "./LiveIndicator";
import { ResyncButton } from "./ResyncButton";

const NAV = [
  { label: "Devices", to: "/devices" },
  { label: "Entities", to: "/entities", disabled: true },
  { label: "Automations", to: "/automations", disabled: true },
  { label: "Areas", to: "/areas", disabled: true },
  { label: "Settings", to: "/settings" },
];

export function Layout() {
  const loc = useLocation();
  const navigate = useNavigate();
  return (
    <AppShell
      header={{ height: 44 }}
      navbar={{ width: 200, breakpoint: "sm" }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={5}>Home Curator</Title>
          <Group gap="xs">
            <ResyncButton />
            <LiveIndicator />
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            label={item.label}
            active={loc.pathname.startsWith(item.to)}
            disabled={item.disabled}
            onClick={(e) => {
              e.preventDefault();
              if (!item.disabled) navigate(item.to);
            }}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
