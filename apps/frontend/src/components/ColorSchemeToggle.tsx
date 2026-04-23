import { ActionIcon, Menu, Tooltip, useMantineColorScheme } from "@mantine/core";
import { IconDeviceDesktop, IconMoon, IconSun } from "@tabler/icons-react";

export function ColorSchemeToggle() {
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  const icon =
    colorScheme === "dark" ? (
      <IconMoon size={18} />
    ) : colorScheme === "light" ? (
      <IconSun size={18} />
    ) : (
      <IconDeviceDesktop size={18} />
    );

  return (
    <Menu shadow="md" width={160} position="bottom-end">
      <Menu.Target>
        <Tooltip label="Color Scheme" withArrow>
          <ActionIcon variant="subtle" aria-label="Color Scheme">
            {icon}
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item
          leftSection={<IconSun size={16} />}
          onClick={() => setColorScheme("light")}
        >
          Light
        </Menu.Item>
        <Menu.Item
          leftSection={<IconMoon size={16} />}
          onClick={() => setColorScheme("dark")}
        >
          Dark
        </Menu.Item>
        <Menu.Item
          leftSection={<IconDeviceDesktop size={16} />}
          onClick={() => setColorScheme("auto")}
        >
          System
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
