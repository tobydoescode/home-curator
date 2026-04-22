import { AppShell, NavLink, Title } from "@mantine/core";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

const NAV = [
  { label: "Devices", to: "/devices" },
  { label: "Entities", to: "/entities", disabled: true },
  { label: "Automations", to: "/automations", disabled: true },
  { label: "Areas", to: "/areas", disabled: true },
  { label: "Settings", to: "/settings/naming-conventions" },
];

export function Layout() {
  const loc = useLocation();
  const navigate = useNavigate();
  return (
    <AppShell navbar={{ width: 200, breakpoint: "sm" }} padding="md">
      <AppShell.Navbar p="sm">
        <Title order={5} mb="sm">
          Home Curator
        </Title>
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
