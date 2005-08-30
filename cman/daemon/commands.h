/******************************************************************************
*******************************************************************************
**
**  Copyright (C) 2005 Red Hat, Inc.  All rights reserved.
**
**  This copyrighted material is made available to anyone wishing to use,
**  modify, copy, or redistribute it subject to the terms and conditions
**  of the GNU General Public License v.2.
**
*******************************************************************************
******************************************************************************/

struct cluster_node;
struct connection;
extern void process_cnxman_message(char *data, int len, char *addr, int addrlen,
				  struct cluster_node *rem_node);

extern int send_to_userport(unsigned char fromport, unsigned char toport,
			    int nodeid, int tgtnodeid,
			    struct totem_ip_address *ais_node,
			    char *recv_buf, int len,
			    int endian_conv);
extern void clean_dead_listeners(void);
extern void unbind_con(struct connection *con);
extern void commands_init(void);
extern int process_command(struct connection *con, int cmd, char *cmdbuf,
			   char **retbuf, int *retlen, int retsize, int offset);
extern int send_joinreq(void);

extern void add_ais_node(struct totem_ip_address *ais_node, uint64_t incarnation, int total_members);
extern void del_ais_node(struct totem_ip_address *ais_node);

extern int config_version;
extern int cluster_members;
