import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

import { MantineProvider, localStorageColorSchemeManager } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { DevicesPage } from "@/pages/Devices/DevicesPage";
import { EntitiesPage } from "@/pages/Entities/EntitiesPage";
import { DeviceSettingsPage } from "@/pages/Settings/DeviceSettings/DeviceSettingsPage";
import { EntitySettingsPage } from "@/pages/Settings/EntitySettings/EntitySettingsPage";
import { ExceptionsPage } from "@/pages/Settings/Exceptions/ExceptionsPage";
import { GlobalPoliciesPage } from "@/pages/Settings/GlobalPolicies/GlobalPoliciesPage";
import { SettingsLayout } from "@/pages/Settings/SettingsLayout";
import { theme } from "@/theme";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

const colorSchemeManager = localStorageColorSchemeManager({
  key: "home-curator:color-scheme",
});

export default function App() {
  return (
    <MantineProvider
      theme={theme}
      defaultColorScheme="auto"
      colorSchemeManager={colorSchemeManager}
    >
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <ModalsProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route path="/" element={<Navigate to="/devices" replace />} />
                <Route path="/devices" element={<DevicesPage />} />
                <Route path="/entities" element={<EntitiesPage />} />
                <Route path="/settings" element={<SettingsLayout />}>
                  <Route index element={<Navigate to="/settings/devices" replace />} />
                  <Route path="devices" element={<DeviceSettingsPage />} />
                  <Route path="entities" element={<EntitySettingsPage />} />
                  <Route path="global" element={<GlobalPoliciesPage />} />
                  <Route path="exceptions" element={<ExceptionsPage />} />
                </Route>
                <Route
                  path="/settings/naming-conventions"
                  element={<Navigate to="/settings/devices" replace />}
                />
                <Route path="*" element={<div>Not Found</div>} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ModalsProvider>
      </QueryClientProvider>
    </MantineProvider>
  );
}
