import { AppShell, Burger, Group, NavLink, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { useLocalStorageBoolean } from "@/hooks/useLocalStorageBoolean";

import { ColorSchemeToggle } from "./ColorSchemeToggle";
import { LiveIndicator } from "./LiveIndicator";
import { ResyncButton } from "./ResyncButton";

const NAV = [
  { label: "Devices", to: "/devices" },
  { label: "Entities", to: "/entities" },
  { label: "Automations", to: "/automations", disabled: true },
  { label: "Areas", to: "/areas", disabled: true },
  { label: "Settings", to: "/settings" },
];

const DESKTOP_OPEN_KEY = "home-curator:sidebar-desktop-opened";

export function Layout() {
  const loc = useLocation();
  const navigate = useNavigate();
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure(false);
  const [desktopOpened, toggleDesktop] = useLocalStorageBoolean(
    DESKTOP_OPEN_KEY,
    true,
  );
  return (
    <AppShell
      header={{ height: 44 }}
      navbar={{
        width: 200,
        breakpoint: "sm",
        collapsed: { desktop: !desktopOpened, mobile: !mobileOpened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              hiddenFrom="sm"
              size="sm"
              aria-label="Toggle Navigation"
            />
            <Burger
              opened={desktopOpened}
              onClick={toggleDesktop}
              visibleFrom="sm"
              size="sm"
              aria-label="Toggle Sidebar"
            />
            <Title order={5}>Home Curator</Title>
          </Group>
          <Group gap="xs">
            <ColorSchemeToggle />
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
