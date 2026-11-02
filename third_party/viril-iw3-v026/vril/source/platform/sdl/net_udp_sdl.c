/*
Copyright (C) 1996-1997 Id Software, Inc.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

*/
// net_udp.c
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

#include "../../nzportable_def.h"
#include "net_udp.h"

#if !defined(_WIN32)
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <arpa/inet.h>
#endif

#include <sys/fcntl.h>
#include <unistd.h>

#ifdef __ANDROID__
extern int Xziel_Android_OnlineActive(void);
extern int Xziel_Android_GameHasPacket(int localPort);
extern int Xziel_Android_GameSend(const unsigned char *data, int len,
    int destinationSlot, int sourcePort, int destinationPort);
extern int Xziel_Android_GamePoll(int localPort, unsigned char *out, int maxLen,
    int *sourceSlot, int *sourcePort);

#define XZIEL_VIRTUAL_NET 0x0A4D0000u

static int Xziel_SocketPort(int socket_fd)
{
    struct sockaddr_in address;
    socklen_t len = sizeof(address);
    if (getsockname(socket_fd, (struct sockaddr *)&address, &len) == -1)
        return 0;
    return ntohs(address.sin_port);
}

static int Xziel_VirtualSlot(const struct qsockaddr *addr)
{
    unsigned int host;
    if (!addr || addr->sa_family != AF_INET)
        return 0;
    host = ntohl(((const struct sockaddr_in *)addr)->sin_addr.s_addr);
    if ((host & 0xFFFFFF00u) != XZIEL_VIRTUAL_NET)
        return 0;
    host &= 0xFFu;
    return (host >= 1u && host <= 4u) ? (int)host : 0;
}

static void Xziel_SetVirtualAddr(struct qsockaddr *addr, int slot, int port)
{
    struct sockaddr_in *internet = (struct sockaddr_in *)addr;
    memset(addr, 0, sizeof(*addr));
    internet->sin_family = AF_INET;
    internet->sin_addr.s_addr = htonl(XZIEL_VIRTUAL_NET | (unsigned int)slot);
    internet->sin_port = htons((unsigned short)port);
}
#endif

extern cvar_t hostname;

static int net_acceptsocket = -1;		// socket for fielding new connections
static int net_controlsocket;
static int net_broadcastsocket = 0;
static struct qsockaddr broadcastaddr;

static unsigned long myAddr;

#include "net_udp.h"

//=============================================================================

int UDP_Init (void)
{
	#if defined(_WIN32)
	WSADATA wsaData;

	if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0)
		return -1;
	#endif

	struct qsockaddr addr;
	char *colon;

	if (COM_CheckParm ("-noudp"))
		return -1;

	#if defined(_WIN32)
		{
			char hostname[256];
			struct hostent *hostentry;

			gethostname(hostname, sizeof(hostname));

			hostentry = gethostbyname(hostname);
			if (hostentry && hostentry->h_addr_list[0])
				myAddr = *(unsigned long *)hostentry->h_addr_list[0];
			else
				myAddr = inet_addr("127.0.0.1");
		}
	#elif defined(__ANDROID__)
		{
			char local_hostname[256] = "localhost";
			struct hostent *hostentry;
			struct in_addr resolved;

			if (gethostname(local_hostname, sizeof(local_hostname)) != 0)
				strcpy(local_hostname, "localhost");
			local_hostname[sizeof(local_hostname) - 1] = 0;

			hostentry = gethostbyname(local_hostname);
			if (hostentry && hostentry->h_addr_list[0]) {
				memcpy(&resolved.s_addr, hostentry->h_addr_list[0], sizeof(resolved.s_addr));
				myAddr = resolved.s_addr;
			} else {
				myAddr = inet_addr("127.0.0.1");
			}
		}
	#else
		myAddr = gethostid();
	#endif

	// if the quake hostname isn't set, set it to the machine name
	if (strcmp(hostname.string, "UNNAMED") == 0)
	{
		char local_hostname[NET_NAMELEN] = "localhost";
		gethostname(local_hostname, sizeof(local_hostname));
		Cvar_Set ("hostname", local_hostname);
	}

	if ((net_controlsocket = UDP_OpenSocket (0)) == -1)
	{
		return -1;
	}

	((struct sockaddr_in *)&broadcastaddr)->sin_family = AF_INET;
	((struct sockaddr_in *)&broadcastaddr)->sin_addr.s_addr = INADDR_BROADCAST;
	((struct sockaddr_in *)&broadcastaddr)->sin_port = htons(net_hostport);

	UDP_GetSocketAddr (net_controlsocket, &addr);
	Q_strcpy(my_tcpip_address,  UDP_AddrToString (&addr));
	colon = Q_strrchr (my_tcpip_address, ':');
	if (colon)
		*colon = 0;

	Con_Printf("UDP Initialized\n");
	tcpipAvailable = true;

	return net_controlsocket;
}

//=============================================================================

void UDP_Shutdown (void)
{
	UDP_Listen (false);
	UDP_CloseSocket (net_controlsocket);
}

//=============================================================================

void UDP_Listen (qboolean state)
{
	// enable listening
	if (state)
	{
		if (net_acceptsocket != -1)
			return;
		if ((net_acceptsocket = UDP_OpenSocket (net_hostport)) == -1)
			Sys_Error ("Unable to open accept socket\n");
		return;
	}

	// disable listening
	if (net_acceptsocket == -1)
		return;
	UDP_CloseSocket (net_acceptsocket);
	net_acceptsocket = -1;
}

//=============================================================================

int UDP_OpenSocket (int port)
{
	int newsocket;
	struct sockaddr_in address;

	if ((newsocket = socket(AF_INET, SOCK_DGRAM, 0)) == -1)
		return -1;

	#if defined(_WIN32)
	u_long mode = 1;
	if (ioctlsocket(newsocket, FIONBIO, &mode) != 0)
		goto ErrorReturn;
	#else
	int flags = fcntl(newsocket, F_GETFL, 0);
	if ( fcntl(newsocket, F_SETFL, flags | O_NONBLOCK) == -1)
		goto ErrorReturn;
	#endif

	address.sin_family = AF_INET;
	address.sin_addr.s_addr = htonl(INADDR_ANY);
	address.sin_port = htons(port);


	if( bind (newsocket, (void *)&address, sizeof(address)) == -1)
		goto ErrorReturn;

	return newsocket;

ErrorReturn:
	#if defined(_WIN32)
	closesocket(newsocket);
	#else
	close (newsocket);
	#endif
	return -1;
}

//=============================================================================

int UDP_CloseSocket (int socket)
{
	if (socket == net_broadcastsocket)
		net_broadcastsocket = 0;

	return close (socket);
}


//=============================================================================
/*
============
PartialIPAddress

this lets you type only as much of the net address as required, using
the local network components to fill in the rest
============
*/
static int PartialIPAddress (char *in, struct qsockaddr *hostaddr)
{
	char buff[256];
	char *b;
	int addr;
	int num;
	int mask;
	int run;
	int port;

	buff[0] = '.';
	b = buff;
	strcpy(buff+1, in);
	if (buff[1] == '.')
		b++;

	addr = 0;
	mask=-1;
	while (*b == '.')
	{
		b++;
		num = 0;
		run = 0;
		while (!( *b < '0' || *b > '9'))
		{
		  num = num*10 + *b++ - '0';
		  if (++run > 3)
		  	return -1;
		}
		if ((*b < '0' || *b > '9') && *b != '.' && *b != ':' && *b != 0)
			return -1;
		if (num < 0 || num > 255)
			return -1;
		mask<<=8;
		addr = (addr<<8) + num;
	}

	if (*b++ == ':')
		port = Q_atoi(b);
	else
		port = net_hostport;

	hostaddr->sa_family = AF_INET;
	((struct sockaddr_in *)hostaddr)->sin_port = htons((short)port);
	((struct sockaddr_in *)hostaddr)->sin_addr.s_addr = (myAddr & htonl(mask)) | htonl(addr);

	return 0;
}
//=============================================================================

int UDP_Connect (int socket, struct qsockaddr *addr)
{
	return 0;
}

//=============================================================================

int UDP_CheckNewConnections (void)
{
	char buf[4096];

	if (net_acceptsocket == -1)
		return -1;

#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		int local_port = Xziel_SocketPort(net_acceptsocket);
		if (local_port > 0 && Xziel_Android_GameHasPacket(local_port))
			return net_acceptsocket;
	}
#endif

	if (recvfrom(net_acceptsocket, buf, 4096, MSG_PEEK, NULL, NULL) > 0)
		return net_acceptsocket;

	return -1;
}

//=============================================================================

int UDP_Read (int socket, byte *buf, int len, struct qsockaddr *addr)
{
	int addrlen = sizeof (struct qsockaddr);
	int ret;

#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		int local_port = Xziel_SocketPort(socket);
		int source_slot = 0;
		int source_port = 0;
		if (local_port > 0) {
			ret = Xziel_Android_GamePoll(local_port, buf, len,
				&source_slot, &source_port);
			if (ret > 0 && source_slot >= 1 && source_slot <= 4) {
				Xziel_SetVirtualAddr(addr, source_slot, source_port);
				return ret;
			}
		}
	}
#endif

	ret = recvfrom(socket, (char *)buf, len, 0,
		(struct sockaddr *)addr, (socklen_t*)&addrlen);
	if (ret == -1 )
		return 0;
	return ret;
}

//=============================================================================

int UDP_MakeSocketBroadcastCapable (int socket)
{
	int enabled = 1;
	#if defined(_WIN32)
	if (setsockopt(socket, SOL_SOCKET, SO_BROADCAST, (const char *)&enabled, sizeof(enabled)) == SOCKET_ERROR)
		return -1;
	#else
	if (setsockopt(socket, SOL_SOCKET, SO_BROADCAST, &enabled, sizeof(enabled)) == -1)
		return -1;
	#endif
	net_broadcastsocket = socket;
	return 0;
}


//=============================================================================

int UDP_Broadcast (int socket, byte *buf, int len)
{
	int ret;

	if (socket != net_broadcastsocket)
	{
		if (net_broadcastsocket != 0)
			Sys_Error("Attempted to use multiple broadcasts sockets\n");
		ret = UDP_MakeSocketBroadcastCapable (socket);
		if (ret == -1)
		{
			Con_Printf("Unable to make socket broadcast capable\n");
			return ret;
		}
	}

	return UDP_Write (socket, buf, len, &broadcastaddr);
}

//=============================================================================

int UDP_Write (int socket, byte *buf, int len, struct qsockaddr *addr)
{
	int ret;

#ifdef __ANDROID__
	if (Xziel_Android_OnlineActive()) {
		int destination_slot = Xziel_VirtualSlot(addr);
		if (destination_slot) {
			int source_port = Xziel_SocketPort(socket);
			int destination_port =
				ntohs(((struct sockaddr_in *)addr)->sin_port);
			if (source_port > 0 &&
				Xziel_Android_GameSend(buf, len, destination_slot,
					source_port, destination_port))
				return len;
			// Keep Vril's normal UDP error contract. A rejected tunnel packet
			// must be -1; returning 0 makes Datagram_SendMessage mark reliable
			// signon data as sent even though Java/Worker dropped it.
			return -1;
		}
	}
#endif

	ret = sendto (socket, (const char *)buf, len, 0,
		(struct sockaddr *)addr, sizeof(struct qsockaddr));
	if (ret == -1 )
		return 0;
	return ret;
}

//=============================================================================

char *UDP_AddrToString (struct qsockaddr *addr)
{
	static char buffer[22];
	int haddr;

	haddr = ntohl(((struct sockaddr_in *)addr)->sin_addr.s_addr);
	sprintf(buffer, "%d.%d.%d.%d:%d", (haddr >> 24) & 0xff, (haddr >> 16) & 0xff, (haddr >> 8) & 0xff, haddr & 0xff, ntohs(((struct sockaddr_in *)addr)->sin_port));
	return buffer;
}

//=============================================================================

int UDP_StringToAddr (char *string, struct qsockaddr *addr)
{
	int ha1, ha2, ha3, ha4, hp;
	int ipaddr;

	sscanf(string, "%d.%d.%d.%d:%d", &ha1, &ha2, &ha3, &ha4, &hp);
	ipaddr = (ha1 << 24) | (ha2 << 16) | (ha3 << 8) | ha4;

	addr->sa_family = AF_INET;
	((struct sockaddr_in *)addr)->sin_addr.s_addr = htonl(ipaddr);
	((struct sockaddr_in *)addr)->sin_port = htons(hp);
	return 0;
}

//=============================================================================

int UDP_GetSocketAddr (int socket, struct qsockaddr *addr)
{
	int addrlen = sizeof(struct qsockaddr);
	unsigned int a;

	Q_memset(addr, 0, sizeof(struct qsockaddr));
	getsockname(socket, (struct sockaddr *)addr, (socklen_t*)&addrlen);
	a = ((struct sockaddr_in *)addr)->sin_addr.s_addr;
	if (a == 0 || a == inet_addr("127.0.0.1"))
		((struct sockaddr_in *)addr)->sin_addr.s_addr = myAddr;

	return 0;
}

//=============================================================================

int UDP_GetNameFromAddr (struct qsockaddr *addr, char *name)
{
	struct hostent *hostentry;

	hostentry = gethostbyaddr ((char *)&((struct sockaddr_in *)addr)->sin_addr, sizeof(struct in_addr), AF_INET);
	if (hostentry)
	{
		Q_strncpy (name, (char *)hostentry->h_name, NET_NAMELEN - 1);
		return 0;
	}

	Q_strcpy (name, UDP_AddrToString (addr));
	return 0;
}

//=============================================================================

int UDP_GetAddrFromName(char *name, struct qsockaddr *addr)
{
	struct hostent *hostentry;

	if (name[0] >= '0' && name[0] <= '9')
		return PartialIPAddress (name, addr);

	hostentry = gethostbyname (name);
	if (!hostentry)
		return -1;

	addr->sa_family = AF_INET;
	((struct sockaddr_in *)addr)->sin_port = htons(net_hostport);
	((struct sockaddr_in *)addr)->sin_addr.s_addr = *(int *)hostentry->h_addr_list[0];

	return 0;
}

//=============================================================================

int UDP_AddrCompare (struct qsockaddr *addr1, struct qsockaddr *addr2)
{
	if (addr1->sa_family != addr2->sa_family)
		return -1;

	if (((struct sockaddr_in *)addr1)->sin_addr.s_addr != ((struct sockaddr_in *)addr2)->sin_addr.s_addr)
		return -1;

	if (((struct sockaddr_in *)addr1)->sin_port != ((struct sockaddr_in *)addr2)->sin_port)
		return 1;

	return 0;
}

//=============================================================================

int UDP_GetSocketPort (struct qsockaddr *addr)
{
	return ntohs(((struct sockaddr_in *)addr)->sin_port);
}


int UDP_SetSocketPort (struct qsockaddr *addr, int port)
{
	((struct sockaddr_in *)addr)->sin_port = htons(port);
	return 0;
}

//=============================================================================
