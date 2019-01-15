#!/usr/bin/python
import utils
import gensio
from remote_termios import *

class Logger:
    def gensio_log(self, level, log):
        print("***%s log: %s" % (level, log))

gensio.gensio_set_log_mask(gensio.GENSIO_LOG_MASK_ALL)
o = gensio.alloc_gensio_selector(Logger());

def test_echo_device():
    print("Test echo device")
    io = utils.alloc_io(o, "serialdev,/dev/ttyEcho0,38400")
    utils.test_dataxfer(io, io, "This is a test string!")
    utils.io_close(io)
    print("  Success!")

def test_serial_pipe_device():
    print("Test serial pipe device")
    io1 = utils.alloc_io(o, "serialdev,/dev/ttyPipeA0,9600")
    io2 = utils.alloc_io(o, "serialdev,/dev/ttyPipeB0,9600")
    utils.test_dataxfer(io1, io2, "This is a test string!")
    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

class TestAccept:
    def __init__(self, o, io1, iostr, tester, name = None,
                 io1_dummy_write = None):
        self.o = o
        if (name):
            self.name = name
        else:
            self.name = iostr
        self.io1 = io1
        self.waiter = gensio.waiter(o)
        self.acc = gensio.gensio_accepter(o, iostr, self);
        self.acc.startup()
        io1.open_s()
        if (io1_dummy_write):
            # For UDP, kick start things.
            io1.write(io1_dummy_write, None)
        self.wait()
        if (io1_dummy_write):
            self.io2.handler.set_compare(io1_dummy_write)
            if (self.io2.handler.wait_timeout(1000)):
                raise Exception(("%s: %s: " % ("test_accept",
                                               self.io2.handler.name)) +
                        ("Timed out waiting for dummy read at byte %d" %
                         self.io2.handler.compared))
        tester(self.io1, self.io2)

    def new_connection(self, acc, io):
        utils.HandleData(self.o, None, io = io, name = self.name)
        self.io2 = io
        self.waiter.wake()

    def accepter_log(self, acc, level, logstr):
        print("***%s LOG: %s: %s" % (level, self.name, logstr))

    def wait(self):
        self.waiter.wait(1)

def do_test(io1, io2):
    utils.test_dataxfer(io1, io2, "This is a test string!")
    print("  Success!")

def ta_tcp():
    print("Test accept tcp")
    io1 = utils.alloc_io(o, "tcp,localhost,3023", do_open = False)
    TestAccept(o, io1, "tcp,3023", do_test)

def ta_udp():
    print("Test accept udp")
    io1 = utils.alloc_io(o, "udp,localhost,3023", do_open = False)
    TestAccept(o, io1, "udp,3023", do_test, io1_dummy_write = "A")

def ta_sctp():
    print("Test accept sctp")
    io1 = utils.alloc_io(o, "sctp,localhost,3023", do_open = False)
    TestAccept(o, io1, "sctp,3023", do_test)
    c = io1.control(0, True, gensio.GENSIO_CONTROL_STREAMS, "")
    if c != "instreams=1,ostreams=1":
        raise Exception("Invalid stream settings: %s" % c)

def ta_ssl_tcp():
    print("Test accept ssl-tcp")
    io1 = utils.alloc_io(o, "ssl(CA=%s/CA.pem),tcp,localhost,3024" % utils.srcdir, do_open = False)
    ta = TestAccept(o, io1, "ssl(key=%s/key.pem,cert=%s/cert.pem),3024" % (utils.srcdir, utils.srcdir), do_test)
    cn = io1.control(0, True, gensio.GENSIO_CONTROL_GET_PEER_CERT_NAME,
                     "-1,CN");
    i = cn.index(',')
    if cn[i+1:] != "ser2net.org":
        raise Exception(
            "Invalid common name in certificate, expected %s, got %s" %
            ("ser2net.org", cn[i+1:]))

def ta_certauth_tcp():
    print("Test accept certauth-tcp")
    io1 = utils.alloc_io(o, "certauth(cert=%s/clientcert.pem,key=%s/clientkey.pem,username=testuser),tcp,localhost,3080" % (utils.srcdir, utils.srcdir), do_open = False)
    ta = TestAccept(o, io1, "certauth(CA=%s/clientcert.pem),3080" % utils.srcdir, do_test)
    cn = io1.control(0, True, gensio.GENSIO_CONTROL_GET_PEER_CERT_NAME,
                     "-1,CN");
    i = cn.index(',')
    if cn[i+1:] != "gensio.org":
        raise Exception(
            "Invalid common name in certificate, expected %s, got %s" %
            ("gensio.org", cn[i+1:]))

def do_telnet_test(io1, io2):
    do_test(io1, io2)
    sio1 = io1.cast_to_sergensio()
    sio2 = io1.cast_to_sergensio()
    io1.read_cb_enable(True);
    io2.read_cb_enable(True);

    io2.handler.set_expected_server_cb("baud", 1000, 2000)
    io1.handler.set_expected_client_cb("baud", 2000)
    sio1.sg_baud(1000, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server baud set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client baud response")

    io2.handler.set_expected_server_cb("datasize", 5, 6)
    io1.handler.set_expected_client_cb("datasize", 6)
    sio1.sg_datasize(5, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server datasize set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client datasize response")

    io2.handler.set_expected_server_cb("parity", 1, 5)
    io1.handler.set_expected_client_cb("parity", 5)
    sio1.sg_parity(1, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server parity set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client parity response")

    io2.handler.set_expected_server_cb("stopbits", 2, 1)
    io1.handler.set_expected_client_cb("stopbits", 1)
    sio1.sg_stopbits(2, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server stopbits set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client stopbits response")

    io2.handler.set_expected_server_cb("flowcontrol", 1, 2)
    io1.handler.set_expected_client_cb("flowcontrol", 2)
    sio1.sg_flowcontrol(1, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server flowcontrol set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client flowcontrol response")

    io2.handler.set_expected_server_cb("iflowcontrol", 3, 4)
    io1.handler.set_expected_client_cb("iflowcontrol", 4)
    sio1.sg_iflowcontrol(3, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server flowcontrol set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client flowcontrol response")

    io2.handler.set_expected_server_cb("sbreak", 2, 1)
    io1.handler.set_expected_client_cb("sbreak", 1)
    sio1.sg_sbreak(2, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server sbreak set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client sbreak response")

    io2.handler.set_expected_server_cb("dtr", 1, 2)
    io1.handler.set_expected_client_cb("dtr", 2)
    sio1.sg_dtr(1, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server dtr set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client dtr response")

    io2.handler.set_expected_server_cb("rts", 2, 1)
    io1.handler.set_expected_client_cb("rts", 1)
    sio1.sg_rts(2, io1.handler)
    if io2.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for server rts set")
    if io1.handler.wait_timeout(1000):
        raise Exception("Timeout waiting for client rts response")
    return

def ta_ssl_telnet():
    print("Test accept ssl telnet")
    io1 = utils.alloc_io(o, "telnet(rfc2217),tcp,localhost,3027",
                         do_open = False)
    ta = TestAccept(o, io1, "telnet(rfc2217=true),3027", do_telnet_test)

def test_modemstate():
    io1str = "serialdev,/dev/ttyPipeA0,9600N81,LOCAL"
    io2str = "serialdev,/dev/ttyPipeB0,9600N81"

    print("serialdev modemstate:\n  io1=%s\n  io2=%s" % (io1str, io2str))

    io1 = utils.alloc_io(o, io1str, do_open = False)
    io2 = utils.alloc_io(o, io2str)

    set_remote_null_modem(io2, False);
    set_remote_modem_ctl(io2, (SERGENSIO_TIOCM_CAR |
                               SERGENSIO_TIOCM_CTS |
                               SERGENSIO_TIOCM_DSR |
                               SERGENSIO_TIOCM_RNG) << 16)

    io1.handler.set_expected_modemstate(0)
    io1.open_s()
    io1.read_cb_enable(True);
    if (io1.handler.wait_timeout(2000)):
        raise Exception("%s: %s: Timed out waiting for modemstate 1" %
                        ("test dtr", io1.handler.name))

    io2.read_cb_enable(True);

    io1.handler.set_expected_modemstate(gensio.SERGENSIO_MODEMSTATE_CD_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CD)
    set_remote_modem_ctl(io2, ((SERGENSIO_TIOCM_CAR << 16) |
                               SERGENSIO_TIOCM_CAR))
    if (io1.handler.wait_timeout(2000)):
        raise Exception("%s: %s: Timed out waiting for modemstate 2" %
                        ("test dtr", io1.handler.name))

    io1.handler.set_expected_modemstate(gensio.SERGENSIO_MODEMSTATE_DSR_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CD |
                                        gensio.SERGENSIO_MODEMSTATE_DSR)
    set_remote_modem_ctl(io2, ((SERGENSIO_TIOCM_DSR << 16) |
                               SERGENSIO_TIOCM_DSR))
    if (io1.handler.wait_timeout(2000)):
        raise Exception("%s: %s: Timed out waiting for modemstate 3" %
                        ("test dtr", io1.handler.name))

    io1.handler.set_expected_modemstate(gensio.SERGENSIO_MODEMSTATE_CTS_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CD |
                                        gensio.SERGENSIO_MODEMSTATE_DSR |
                                        gensio.SERGENSIO_MODEMSTATE_CTS)
    set_remote_modem_ctl(io2, ((SERGENSIO_TIOCM_CTS << 16) |
                               SERGENSIO_TIOCM_CTS))
    if (io1.handler.wait_timeout(2000)):
        raise Exception("%s: %s: Timed out waiting for modemstate 4" %
                        ("test dtr", io1.handler.name))

    io1.handler.set_expected_modemstate(gensio.SERGENSIO_MODEMSTATE_RI_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CD |
                                        gensio.SERGENSIO_MODEMSTATE_DSR |
                                        gensio.SERGENSIO_MODEMSTATE_CTS |
                                        gensio.SERGENSIO_MODEMSTATE_RI)
    set_remote_modem_ctl(io2, ((SERGENSIO_TIOCM_RNG << 16) |
                               SERGENSIO_TIOCM_RNG))
    if (io1.handler.wait_timeout(2000)):
        raise Exception("%s: %s: Timed out waiting for modemstate 5" %
                        ("test dtr", io1.handler.name))

    io1.handler.set_expected_modemstate(gensio.SERGENSIO_MODEMSTATE_RI_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CD_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_DSR_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CTS_CHANGED)
    set_remote_modem_ctl(io2, (SERGENSIO_TIOCM_CAR |
                               SERGENSIO_TIOCM_CTS |
                               SERGENSIO_TIOCM_DSR |
                               SERGENSIO_TIOCM_RNG) << 16)
    if (io1.handler.wait_timeout(2000)):
        raise Exception("%s: %s: Timed out waiting for modemstate 6" %
                        ("test dtr", io1.handler.name))

    io1.handler.set_expected_modemstate(gensio.SERGENSIO_MODEMSTATE_CD_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_DSR_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CTS_CHANGED |
                                        gensio.SERGENSIO_MODEMSTATE_CD |
                                        gensio.SERGENSIO_MODEMSTATE_DSR |
                                        gensio.SERGENSIO_MODEMSTATE_CTS)
    set_remote_null_modem(io2, True);
    if (io1.handler.wait_timeout(2000)):
        raise Exception("%s: %s: Timed out waiting for modemstate 7" %
                        ("test dtr", io1.handler.name))

    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")
    return

def test_stdio_basic():
    print("Test stdio basic echo")
    io = utils.alloc_io(o, "stdio,cat", chunksize = 64)
    utils.test_dataxfer(io, io, "This is a test string!")
    utils.io_close(io)
    print("  Success!")

def test_stdio_basic_stderr():
    print("Test stdio basic stderr echo")
    io = utils.alloc_io(o, "stdio,sh -c 'cat 1>&2'", chunksize = 64)
    io.handler.ignore_input = True
    io.read_cb_enable(True)
    err = io.open_channel_s(None, None)
    utils.HandleData(o, "stderr", chunksize = 64, io = err)
    utils.test_dataxfer(io, err, "This is a test string!")
    utils.io_close(io)
    utils.io_close(err)
    print("  Success!")

def test_stdio_small():
    print("Test stdio small echo")
    rb = gensio.get_random_bytes(512)
    io = utils.alloc_io(o, "stdio,cat", chunksize = 64)
    utils.test_dataxfer(io, io, rb)
    utils.io_close(io)
    print("  Success!")

def do_small_test(io1, io2):
    rb = gensio.get_random_bytes(512)
    print("  testing io1 to io2")
    utils.test_dataxfer(io1, io2, rb)
    print("  testing io2 to io1")
    utils.test_dataxfer(io2, io1, rb)
    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

def test_tcp_small():
    print("Test tcp small")
    io1 = utils.alloc_io(o, "tcp,localhost,3025", do_open = False,
                         chunksize = 64)
    ta = TestAccept(o, io1, "tcp,3025", do_small_test)

def do_urgent_test(io1, io2):
    rb = "A" # We only get one byte of urgent data.
    print("  testing io1 to io2")
    utils.test_dataxfer_oob(io1, io2, rb)
    print("  testing io2 to io1")
    utils.test_dataxfer_oob(io2, io1, rb)
    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

def test_tcp_urgent():
    print("Test tcp urgent")
    io1 = utils.alloc_io(o, "tcp,localhost,3028", do_open = False,
                         chunksize = 64)
    ta = TestAccept(o, io1, "tcp,3028", do_urgent_test)

def test_sctp_small():
    print("Test sctp small")
    io1 = utils.alloc_io(o, "sctp,localhost,3025", do_open = False,
                         chunksize = 64)
    ta = TestAccept(o, io1, "sctp,3025", do_small_test)

def do_stream_test(io1, io2):
    rb = gensio.get_random_bytes(10)
    print("  testing io1 to io2")
    utils.test_dataxfer_stream(io1, io2, rb, 2)
    print("  testing io2 to io1")
    utils.test_dataxfer_stream(io2, io1, rb, 1)
    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

def test_sctp_streams():
    print("Test sctp streams")
    io1 = utils.alloc_io(o, "sctp(instreams=2,ostreams=3),localhost,3030",
                         do_open = False, chunksize = 64)
    ta = TestAccept(o, io1, "sctp(instreams=3,ostreams=2),3030", do_stream_test)

def do_oob_test(io1, io2):
    rb = gensio.get_random_bytes(512)
    print("  testing io1 to io2")
    utils.test_dataxfer_oob(io1, io2, rb)
    print("  testing io2 to io1")
    utils.test_dataxfer_oob(io2, io1, rb)
    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

def test_sctp_oob():
    print("Test sctp oob")
    io1 = utils.alloc_io(o, "sctp,localhost,3031",
                         do_open = False, chunksize = 64)
    ta = TestAccept(o, io1, "sctp,3031", do_oob_test)

def test_telnet_small():
    print("Test telnet small")
    io1 = utils.alloc_io(o, "telnet,tcp,localhost,3026", do_open = False,
                         chunksize = 64)
    ta = TestAccept(o, io1, "telnet(rfc2217=true),3026", do_small_test)

import ipmisimdaemon
def test_ipmisol_small():
    print("Test ipmisol small")
    isim = ipmisimdaemon.IPMISimDaemon(o)
    io1 = utils.alloc_io(o, "serialdev,/dev/ttyPipeA0,9600")
    io2 = utils.alloc_io(o, "ipmisol,lan -U ipmiusr -P test -p 9001 localhost,9600")
    utils.test_dataxfer(io1, io2, "This is a test string!")
    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

def test_ipmisol_large():
    print("Test ipmisol large")
    isim = ipmisimdaemon.IPMISimDaemon(o)
    io1 = utils.alloc_io(o, "serialdev,/dev/ttyPipeA0,115200")
    io2 = utils.alloc_io(o, "ipmisol,lan -U ipmiusr -P test -p 9001 localhost,115200")
    rb = gensio.get_random_bytes(104857)
    utils.test_dataxfer(io1, io2, rb, timeout=10000)
    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

def test_rs485():
    io1str = "serialdev,/dev/ttyPipeA0,9600N81,LOCAL,rs485=103:495"
    io2str = "serialdev,/dev/ttyPipeB0,9600N81"

    print("serialdev rs485:\n  io1=%s\n  io2=%s" % (io1str, io2str))

    io1 = utils.alloc_io(o, io1str)
    io2 = utils.alloc_io(o, io2str)

    rs485 = get_remote_rs485(io2)
    check_rs485 = "103 495 enabled"
    if rs485 != check_rs485:
        raise Exception("%s: %s: Modemstate was not '%s', it was '%s'" %
                        ("test rs485", io1.handler.name, check_rs485, rs485))

    utils.io_close(io1)
    utils.io_close(io2)
    print("  Success!")

class TestAcceptConnect:
    def __init__(self, o, iostr, io2str, io3str, tester, name = None,
                 io1_dummy_write = None, CA=None):
        self.o = o
        if (name):
            self.name = name
        else:
            self.name = iostr
        self.waiter = gensio.waiter(o)
        self.acc = gensio.gensio_accepter(o, iostr, self);
        self.acc.startup()
        self.acc2 = gensio.gensio_accepter(o, io2str, self);
        self.acc2.startup()
        self.io1 = self.acc2.str_to_gensio(io3str, None);
        self.CA = CA
        h = utils.HandleData(o, io3str, io = self.io1)
        self.io1.open_s()
        if (io1_dummy_write):
            # For UDP, kick start things.
            self.io1.write(io1_dummy_write, None)
        self.wait()
        if (io1_dummy_write):
            self.io2.handler.set_compare(io1_dummy_write)
            if (self.io2.handler.wait_timeout(1000)):
                raise Exception(("%s: %s: " % ("test_accept",
                                               self.io2.handler.name)) +
                        ("Timed out waiting for dummy read at byte %d" %
                         self.io2.handler.compared))
        tester(self.io1, self.io2)

    def new_connection(self, acc, io):
        utils.HandleData(self.o, None, io = io, name = self.name)
        self.io2 = io
        self.waiter.wake()

    def precert_verify(self, acc, io):
        if self.CA:
            io.control(0, False, gensio.GENSIO_CONTROL_CERT_AUTH, self.CA)
            return 0
        return gensio.ENOTSUP

    def accepter_log(self, acc, level, logstr):
        print("***%s LOG: %s: %s" % (level, self.name, logstr))

    def wait(self):
        self.waiter.wait(1)

def test_tcp_acc_connect():
    print("Test tcp accepter connect")
    ta = TestAcceptConnect(o, "tcp,3040", "tcp,3041", "tcp,localhost,3040",
                           do_small_test)

def test_udp_acc_connect():
    print("Test udp accepter connect")
    ta = TestAcceptConnect(o, "udp,3040", "udp,3041", "udp,localhost,3040",
                           do_small_test, io1_dummy_write = "A")

def test_sctp_acc_connect():
    print("Test sctp accepter connect")
    ta = TestAcceptConnect(o, "sctp,3040", "sctp,3041", "sctp,localhost,3040",
                           do_small_test)

def test_telnet_sctp_acc_connect():
    print("Test telnet over sctp accepter connect")
    ta = TestAcceptConnect(o, "telnet,sctp,3042", "telnet,sctp,3043",
                           "telnet,sctp,localhost,3042", do_small_test)

def test_ssl_sctp_acc_connect():
    print("Test ssl over sctp accepter connect")
    goterr = False
    try:
        ta = TestAcceptConnect(o,
                "ssl(key=%s/key.pem,cert=%s/cert.pem,clientauth),sctp,3044"
                               % (utils.srcdir, utils.srcdir),
                "ssl(key=%s/key.pem,cert=%s/cert.pem),sctp,3045"
                           % (utils.srcdir, utils.srcdir),
                "ssl(CA=%s/CA.pem),sctp,localhost,3044" % utils.srcdir,
                           do_small_test)
    except Exception as E:
        if str(E) != "gensio:open_s: Communication error on send":
            raise
        print "  Success checking no client cert"
        goterr = True
    if not goterr:
        raise Exception("Did not get error on no client certificate.")
    
    goterr = False
    try:
        ta = TestAcceptConnect(o,
                "ssl(key=%s/key.pem,cert=%s/cert.pem,clientauth),sctp,3090"
                               % (utils.srcdir, utils.srcdir),
                "ssl(key=%s/key.pem,cert=%s/cert.pem),sctp,3091"
                               % (utils.srcdir, utils.srcdir),
                "ssl(CA=%s/CA.pem,key=%s/clientkey.pem,cert=%s/clientcert.pem)"
                ",sctp,localhost,3090"
                               % (utils.srcdir, utils.srcdir, utils.srcdir),
                           do_small_test)
    except Exception as E:
        if str(E) != "gensio:open_s: Communication error on send":
            raise
        print "  Success checking invalid client cert"
        goterr = True
    if not goterr:
        raise Exception("Did not get error on invalid client certificate.")
    
    ta = TestAcceptConnect(o,
                "ssl(key=%s/key.pem,cert=%s/cert.pem,clientauth),sctp,3092"
                               % (utils.srcdir, utils.srcdir),
                "ssl(key=%s/key.pem,cert=%s/cert.pem),sctp,3093"
                               % (utils.srcdir, utils.srcdir),
                "ssl(CA=%s/CA.pem,key=%s/clientkey.pem,cert=%s/clientcert.pem)"
                ",sctp,localhost,3092"
                               % (utils.srcdir, utils.srcdir, utils.srcdir),
                           do_small_test, CA="%s/clientcert.pem" % utils.srcdir)

def test_certauth_sctp_acc_connect():
    print("Test certauth over sctp accepter connect")
    goterr = False
    try:
        ta = TestAcceptConnect(o,
                "certauth(CA=%s/clientcert.pem),sctp,3081" % utils.srcdir,
                "certauth(CA=%s/clientcert.pem),sctp,3082" % utils.srcdir,
                "certauth(cert=%s/cert.pem,key=%s/key.pem,username=test1),sctp,localhost,3081" % (utils.srcdir, utils.srcdir),
                           do_small_test)
    except Exception as E:
        if str(E) != "gensio:open_s: Communication error on send":
            raise
        print "  Success checking invalid client cert"
        goterr = True
    if not goterr:
        raise Exception("Did not get error on invalid client certificate.")

    ta = TestAcceptConnect(o,
                "certauth(),sctp,3083",
                "certauth(),sctp,3084",
                "certauth(cert=%s/clientcert.pem,key=%s/clientkey.pem,username=test1),sctp,localhost,3083" % (utils.srcdir, utils.srcdir),
                           do_small_test, CA="%s/clientcert.pem" % utils.srcdir)

test_echo_device()
test_serial_pipe_device()
test_stdio_basic()
test_stdio_basic_stderr()
test_stdio_small()
ta_tcp()
ta_udp()
ta_ssl_tcp()
ta_certauth_tcp()
ta_sctp()
test_modemstate()
test_tcp_small()
test_tcp_urgent()
test_telnet_small()
test_sctp_small()
test_sctp_streams()
test_sctp_oob()
test_ipmisol_small()
ta_ssl_telnet()

test_tcp_acc_connect()
test_udp_acc_connect()
test_sctp_acc_connect()
test_telnet_sctp_acc_connect()
test_ssl_sctp_acc_connect()
test_certauth_sctp_acc_connect()

test_ipmisol_large()
test_rs485()
