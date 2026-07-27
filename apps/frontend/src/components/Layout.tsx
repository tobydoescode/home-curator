import { AppShell, Burger, Group, NavLink, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { Link, Outlet, useLocation } from "react-router-dom";

import { useLocalStorageBoolean } from "@/hooks/useLocalStorageBoolean";

import { ColorSchemeToggle } from "./ColorSchemeToggle";
import { LiveIndicator } from "./LiveIndicator";
import { ResyncButton } from "./ResyncButton";

const NAV = [
  { label: "Devices", to: "/devices" },
  { label: "Entities", to: "/entities" },
  { label: "Settings", to: "/settings" },
];

const DESKTOP_OPEN_KEY = "home-curator:sidebar-desktop-opened";

export function Layout() {
  const loc = useLocation();
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
          // `component={Link}` renders a real anchor with a resolved href, so
          // these are announced as links, reachable by keyboard, and open in a
          // new tab on middle-click. Previously they were anchors with no href
          // and an onClick that called preventDefault, which has none of that.
          // React Router's Link also honours the ingress basename.
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={item.label}
            active={loc.pathname.startsWith(item.to)}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
