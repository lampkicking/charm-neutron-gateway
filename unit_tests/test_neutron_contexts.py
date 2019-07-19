
import io

from contextlib import contextmanager

from mock import (
    MagicMock,
    patch
)
import neutron_contexts

from test_utils import (
    CharmTestCase
)

TO_PATCH = [
    'config',
    'eligible_leader',
    'unit_get',
    'network_get_primary_address',
    'os_release',
]


@contextmanager
def patch_open():
    '''Patch open() to allow mocking both open() itself and the file that is
    yielded.

    Yields the mock for "open" and "file", respectively.'''
    mock_open = MagicMock(spec=open)
    mock_file = MagicMock(spec=io.FileIO)

    @contextmanager
    def stub_open(*args, **kwargs):
        mock_open(*args, **kwargs)
        yield mock_file

    with patch('builtins.open', stub_open):
        yield mock_open, mock_file


class DummyNeutronAPIContext():

    def __init__(self, return_value):
        self.return_value = return_value

    def __call__(self):
        return self.return_value


class TestL3AgentContext(CharmTestCase):

    def setUp(self):
        super(TestL3AgentContext, self).setUp(neutron_contexts,
                                              TO_PATCH)
        self.network_get_primary_address.side_effect = NotImplementedError
        self.config.side_effect = self.test_config.get

    @patch('neutron_contexts.NeutronAPIContext')
    def test_new_ext_network(self, _NeutronAPIContext):
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': False,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 })
        self.test_config.set('run-internal-router', 'none')
        self.test_config.set('external-network-id', '')
        self.eligible_leader.return_value = False
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'external_configuration_new': True,
                          'handle_internal_only_router': False,
                          'plugin': 'ovs'})

    @patch('neutron_contexts.NeutronAPIContext')
    def test_old_ext_network(self, _NeutronAPIContext):
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': False,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 })
        self.test_config.set('run-internal-router', 'none')
        self.test_config.set('ext-port', 'eth1')
        self.eligible_leader.return_value = False
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'handle_internal_only_router': False,
                          'plugin': 'ovs'})

    @patch('neutron_contexts.NeutronAPIContext')
    def test_hior_leader(self, _NeutronAPIContext):
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': False,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 })
        self.test_config.set('run-internal-router', 'leader')
        self.test_config.set('external-network-id', 'netid')
        self.eligible_leader.return_value = True
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'handle_internal_only_router': True,
                          'ext_net_id': 'netid',
                          'plugin': 'ovs'})

    @patch('neutron_contexts.NeutronAPIContext')
    def test_hior_all(self, _NeutronAPIContext):
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': False,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 })
        self.test_config.set('run-internal-router', 'all')
        self.test_config.set('external-network-id', 'netid')
        self.eligible_leader.return_value = True
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'handle_internal_only_router': True,
                          'ext_net_id': 'netid',
                          'plugin': 'ovs'})

    @patch('neutron_contexts.NeutronAPIContext')
    def test_dvr(self, _NeutronAPIContext):
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': True,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 })
        self.assertEqual(neutron_contexts.L3AgentContext()()['agent_mode'],
                         'dvr_snat')


class TestNeutronGatewayContext(CharmTestCase):

    def setUp(self):
        super(TestNeutronGatewayContext, self).setUp(neutron_contexts,
                                                     TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.maxDiff = None

    @patch('neutron_utils.config')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_all(self, _secret, _rids, _runits, _rget, mock_config):
        rdata = {'l2-population': 'True',
                 'enable-dvr': 'True',
                 'overlay-network-type': 'gre',
                 'enable-l3ha': 'True',
                 'enable-qos': 'True',
                 'network-device-mtu': 9000,
                 'dns-domain': 'openstack.example.'}
        self.test_config.set('plugin', 'ovs')
        self.test_config.set('debug', False)
        self.test_config.set('verbose', True)
        self.test_config.set('instance-mtu', 1420)
        self.test_config.set('dnsmasq-flags', 'dhcp-userclass=set:ipxe,iPXE,'
                                              'dhcp-match=set:ipxe,175')
        self.test_config.set('dns-servers', '8.8.8.8,4.4.4.4')
        self.test_config.set('vlan-ranges',
                             'physnet1:1000:2000 physnet2:2001:3000')
        self.test_config.set('flat-network-providers', 'physnet3 physnet4')

        def config_side_effect(key):
            return {
                'customize-failure-domain': False,
                'default-availability-zone': 'nova',
            }[key]
        mock_config.side_effect = config_side_effect

        self.network_get_primary_address.side_effect = NotImplementedError
        self.unit_get.return_value = '10.5.0.1'
        # Provided by neutron-api relation
        _rids.return_value = ['neutron-plugin-api:0']
        _runits.return_value = ['neutron-api/0']
        _rget.side_effect = lambda *args, **kwargs: rdata
        _secret.return_value = 'testsecret'
        ctxt = neutron_contexts.NeutronGatewayContext()()
        self.assertEqual(ctxt, {
            'shared_secret': 'testsecret',
            'enable_dvr': True,
            'enable_l3ha': True,
            'dns_servers': '8.8.8.8,4.4.4.4',
            'extension_drivers': 'qos',
            'dns_domain': 'openstack.example.',
            'local_ip': '10.5.0.1',
            'instance_mtu': 1420,
            'core_plugin': "ml2",
            'plugin': 'ovs',
            'debug': False,
            'verbose': True,
            'l2_population': True,
            'overlay_network_type': 'gre',
            'report_interval': 30,
            'rpc_response_timeout': 60,
            'bridge_mappings': 'physnet1:br-data',
            'network_providers': 'physnet3,physnet4',
            'vlan_ranges': 'physnet1:1000:2000,physnet2:2001:3000',
            'network_device_mtu': 9000,
            'veth_mtu': 9000,
            'enable_isolated_metadata': False,
            'enable_metadata_network': False,
            'dnsmasq_flags': {
                'dhcp-userclass': 'set:ipxe,iPXE',
                'dhcp-match': 'set:ipxe,175'
            },
            'availability_zone': 'nova',
        })

    @patch('neutron_utils.config')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_all_network_spaces(self, _secret, _rids, _runits, _rget,
                                mock_config):
        rdata = {'l2-population': 'True',
                 'enable-dvr': 'True',
                 'overlay-network-type': 'gre',
                 'enable-l3ha': 'True',
                 'enable-qos': 'True',
                 'network-device-mtu': 9000,
                 'dns-domain': 'openstack.example.'}
        self.test_config.set('plugin', 'ovs')
        self.test_config.set('debug', False)
        self.test_config.set('verbose', True)
        self.test_config.set('instance-mtu', 1420)
        self.test_config.set('dnsmasq-flags', 'dhcp-userclass=set:ipxe,iPXE,'
                                              'dhcp-match=set:ipxe,175')
        self.test_config.set('vlan-ranges',
                             'physnet1:1000:2000 physnet2:2001:3000')
        self.test_config.set('flat-network-providers', 'physnet3 physnet4')

        def config_side_effect(key):
            return {
                'customize-failure-domain': False,
                'default-availability-zone': 'nova',
            }[key]
        mock_config.side_effect = config_side_effect

        self.network_get_primary_address.return_value = '192.168.20.2'
        self.unit_get.return_value = '10.5.0.1'
        # Provided by neutron-api relation
        _rids.return_value = ['neutron-plugin-api:0']
        _runits.return_value = ['neutron-api/0']
        _rget.side_effect = lambda *args, **kwargs: rdata
        _secret.return_value = 'testsecret'
        ctxt = neutron_contexts.NeutronGatewayContext()()
        self.assertEqual(ctxt, {
            'shared_secret': 'testsecret',
            'enable_dvr': True,
            'enable_l3ha': True,
            'dns_servers': None,
            'extension_drivers': 'qos',
            'dns_domain': 'openstack.example.',
            'local_ip': '192.168.20.2',
            'instance_mtu': 1420,
            'core_plugin': "ml2",
            'plugin': 'ovs',
            'debug': False,
            'verbose': True,
            'l2_population': True,
            'overlay_network_type': 'gre',
            'report_interval': 30,
            'rpc_response_timeout': 60,
            'bridge_mappings': 'physnet1:br-data',
            'network_providers': 'physnet3,physnet4',
            'vlan_ranges': 'physnet1:1000:2000,physnet2:2001:3000',
            'network_device_mtu': 9000,
            'veth_mtu': 9000,
            'enable_isolated_metadata': False,
            'enable_metadata_network': False,
            'dnsmasq_flags': {
                'dhcp-userclass': 'set:ipxe,iPXE',
                'dhcp-match': 'set:ipxe,175'
            },
            'availability_zone': 'nova',
        })

    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_dhcp_settings(self, _secret, _rids, _runits, _rget):
        self.test_config.set('enable-isolated-metadata', True)
        self.test_config.set('enable-metadata-network', True)
        self.network_get_primary_address.return_value = '192.168.20.2'
        self.unit_get.return_value = '10.5.0.1'
        ctxt = neutron_contexts.NeutronGatewayContext()()
        self.assertTrue(ctxt['enable_isolated_metadata'])
        self.assertTrue(ctxt['enable_metadata_network'])

    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_dhcp_setting_plug_override(self, _secret, _rids, _runits, _rget):
        self.test_config.set('plugin', 'nsx')
        self.test_config.set('enable-isolated-metadata', False)
        self.test_config.set('enable-metadata-network', False)
        self.network_get_primary_address.return_value = '192.168.20.2'
        self.unit_get.return_value = '10.5.0.1'
        ctxt = neutron_contexts.NeutronGatewayContext()()
        self.assertTrue(ctxt['enable_isolated_metadata'])
        self.assertTrue(ctxt['enable_metadata_network'])

    @patch('neutron_utils.config')
    @patch('os.environ.get')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_availability_zone_no_juju_with_env(self, _secret, _rids,
                                                _runits, _rget,
                                                mock_get,
                                                mock_config):
        def environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': 'az1',
                'PATH': 'foobar',
            }[key]
        mock_get.side_effect = environ_get_side_effect

        def config_side_effect(key):
            return {
                'customize-failure-domain': False,
                'default-availability-zone': 'nova',
            }[key]

        mock_config.side_effect = config_side_effect
        context = neutron_contexts.NeutronGatewayContext()
        self.assertEqual(
            'nova', context()['availability_zone'])

    @patch('neutron_utils.config')
    @patch('os.environ.get')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_availability_zone_no_juju_no_env(self, _secret, _rids,
                                              _runits, _rget,
                                              mock_get, mock_config):
        def environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': '',
                'PATH': 'foobar',
            }[key]
        mock_get.side_effect = environ_get_side_effect

        def config_side_effect(key):
            return {
                'customize-failure-domain': False,
                'default-availability-zone': 'nova',
            }[key]

        mock_config.side_effect = config_side_effect
        context = neutron_contexts.NeutronGatewayContext()

        self.assertEqual(
            'nova', context()['availability_zone'])

    @patch('neutron_utils.config')
    @patch('os.environ.get')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_availability_zone_juju(self, _secret, _rids,
                                    _runits, _rget,
                                    mock_get, mock_config):
        def environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': 'az1',
                'PATH': 'foobar',
            }[key]
        mock_get.side_effect = environ_get_side_effect

        mock_config.side_effect = self.test_config.get
        self.test_config.set('customize-failure-domain', True)
        context = neutron_contexts.NeutronGatewayContext()
        self.assertEqual(
            'az1', context()['availability_zone'])


class TestSharedSecret(CharmTestCase):

    def setUp(self):
        super(TestSharedSecret, self).setUp(neutron_contexts,
                                            TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.network_get_primary_address.side_effect = NotImplementedError

    @patch('os.path')
    @patch('uuid.uuid4')
    def test_secret_created_stored(self, _uuid4, _path):
        _path.exists.return_value = False
        _uuid4.return_value = 'secret_thing'
        with patch_open() as (_open, _file):
            self.assertEqual(neutron_contexts.get_shared_secret(),
                             'secret_thing')
            _open.assert_called_with(
                neutron_contexts.SHARED_SECRET.format('neutron'), 'w')
            _file.write.assert_called_with('secret_thing')

    @patch('os.path')
    def test_secret_retrieved(self, _path):
        _path.exists.return_value = True
        with patch_open() as (_open, _file):
            _file.read.return_value = 'secret_thing\n'
            self.assertEqual(neutron_contexts.get_shared_secret(),
                             'secret_thing')
            _open.assert_called_with(
                neutron_contexts.SHARED_SECRET.format('neutron'), 'r')


class TestMisc(CharmTestCase):

    def setUp(self):
        super(TestMisc,
              self).setUp(neutron_contexts,
                          TO_PATCH)

    def test_core_plugin_ml2(self):
        self.config.return_value = 'ovs'
        self.assertEqual(neutron_contexts.core_plugin(),
                         neutron_contexts.NEUTRON_ML2_PLUGIN)


class TestNovaMetadataContext(CharmTestCase):

    def setUp(self):
        super(TestNovaMetadataContext, self).setUp(neutron_contexts,
                                                   TO_PATCH)
        self.config.side_effect = self.test_config.get

    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_vendordata_static(self, _relation_ids, _get_shared_secret,
                               _get_local_ip):
        _get_shared_secret.return_value = 'asecret'
        _get_local_ip.return_value = '127.0.0.1'
        _relation_ids.return_value = []
        _vdata = '{"good": "json"}'
        self.os_release.return_value = 'pike'

        self.test_config.set('vendor-data', _vdata)
        ctxt = neutron_contexts.NovaMetadataContext()()

        self.assertTrue(ctxt['vendor_data'])
<<<<<<< HEAD
        self.assertEqual(ctxt['vendordata_providers'], ['StaticJSON'])
=======
        self.assertEqual(ctxt['vendordata_providers'], 'StaticJSON')
>>>>>>> 9733743501c1abd82e31c4e6c6cb14faefdc05a8

    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_vendordata_dynamic(self, _relation_ids, _get_shared_secret,
                                _get_local_ip):
        _get_shared_secret.return_value = 'asecret'
        _get_local_ip.return_value = '127.0.0.1'
        _relation_ids.return_value = []
        _vdata_url = 'http://example.org/vdata'
        self.os_release.return_value = 'pike'

        self.test_config.set('vendor-data-url', _vdata_url)
        ctxt = neutron_contexts.NovaMetadataContext()()

        self.assertEqual(ctxt['vendor_data_url'], _vdata_url)
<<<<<<< HEAD
        self.assertEqual(ctxt['vendordata_providers'], ['DynamicJSON'])
=======
        self.assertEqual(ctxt['vendordata_providers'], 'DynamicJSON')
>>>>>>> 9733743501c1abd82e31c4e6c6cb14faefdc05a8

    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_vendordata_static_and_dynamic(self, _relation_ids,
                                           _get_shared_secret, _get_local_ip):
        _get_shared_secret.return_value = 'asecret'
        _get_local_ip.return_value = '127.0.0.1'
        _relation_ids.return_value = []
        _vdata = '{"good": "json"}'
        _vdata_url = 'http://example.org/vdata'
        self.os_release.return_value = 'pike'

        self.test_config.set('vendor-data', _vdata)
        self.test_config.set('vendor-data-url', _vdata_url)
        ctxt = neutron_contexts.NovaMetadataContext()()

        self.assertTrue(ctxt['vendor_data'])
        self.assertEqual(ctxt['vendor_data_url'], _vdata_url)
<<<<<<< HEAD
        self.assertEqual(ctxt['vendordata_providers'], ['StaticJSON',
                                                        'DynamicJSON'])
=======
        self.assertEqual(ctxt['vendordata_providers'],
                         'StaticJSON,DynamicJSON')
>>>>>>> 9733743501c1abd82e31c4e6c6cb14faefdc05a8

    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_vendordata_mitaka(self, _relation_ids, _get_shared_secret,
                               _get_local_ip):
        _get_shared_secret.return_value = 'asecret'
        _get_local_ip.return_value = '127.0.0.1'
        _relation_ids.return_value = []
        _vdata_url = 'http://example.org/vdata'
        self.os_release.return_value = 'mitaka'

        self.test_config.set('vendor-data-url', _vdata_url)
        ctxt = neutron_contexts.NovaMetadataContext()()
        self.assertEqual(
            ctxt,
            {
                'nova_metadata_host': '127.0.0.1',
                'nova_metadata_port': '8775',
                'nova_metadata_protocol': 'http',
                'shared_secret': 'asecret',
<<<<<<< HEAD
                'vendordata_providers': []})
=======
                'vendordata_providers': ''})
>>>>>>> 9733743501c1abd82e31c4e6c6cb14faefdc05a8

    @patch.object(neutron_contexts, 'relation_get')
    @patch.object(neutron_contexts, 'related_units')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_NovaMetadataContext(self, _relation_ids, _related_units,
                                 _relation_get):
        _relation_ids.return_value = ['rid:1']
        _related_units.return_value = ['nova-cloud-contoller/0']
        _relation_get.return_value = {
            'nova-metadata-host': '10.0.0.10',
            'nova-metadata-port': '8775',
            'nova-metadata-protocol': 'http',
            'shared-metadata-secret': 'auuid'}
        self.os_release.return_value = 'queens'

        self.assertEqual(
            neutron_contexts.NovaMetadataContext()(),
            {
                'nova_metadata_host': '10.0.0.10',
                'nova_metadata_port': '8775',
                'nova_metadata_protocol': 'http',
                'shared_secret': 'auuid',
<<<<<<< HEAD
                'vendordata_providers': []})
=======
                'vendordata_providers': ''})
>>>>>>> 9733743501c1abd82e31c4e6c6cb14faefdc05a8

    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_NovaMetadataContext_legacy(self, _relation_ids,
                                        _get_shared_secret,
                                        _get_local_ip):
        _relation_ids.return_value = []
        _get_shared_secret.return_value = 'buuid'
        _get_local_ip.return_value = '127.0.0.1'
        self.os_release.return_value = 'pike'
        self.assertEqual(
            neutron_contexts.NovaMetadataContext()(),
            {
                'nova_metadata_host': '127.0.0.1',
                'nova_metadata_port': '8775',
                'nova_metadata_protocol': 'http',
                'shared_secret': 'buuid',
<<<<<<< HEAD
                'vendordata_providers': []})
=======
                'vendordata_providers': ''})
>>>>>>> 9733743501c1abd82e31c4e6c6cb14faefdc05a8
