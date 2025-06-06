
# converts node template data into whatsapp tenant data
def convert_flow(flow, tenant):
    fields = []

    # Extract tenant-specific catalog ID if available
    if tenant.catalog_id != None:
        catalog_id = tenant.catalog_id
    try:
        print("Received flow: ", flow)
        node_blocks = flow['nodes']
        edges = flow['edges']

        nodes = []
        adjList = []
        current_id = 0  # Sequential ID counter for new node format

        # Process each node in the input flow
        for node_block in node_blocks:

            # Skip start nodes as they're handled in edge processing
            if node_block['type'] == "start":
                continue;
            
            # Handle Question Nodes
            if node_block['type'] == 'askQuestion':
                data = node_block['data']
                base_node = {
                    "oldIndex": node_block["id"],
                    "id": current_id,
                    "body": data['question'] or "Choose Option:"
                }

                # Add optional delay if present
                delay = data.get('delay')
                if delay:
                    base_node['delay'] = delay

                # Collect variables for data capture
                if data['variable'] and data['dataType']: 
                    fields.append({
                        'field_name': data['variable'] or None,
                        'field_type': data['dataType'] or None
                    })
                    base_node.update({
                        'variable': data['variable'],
                        'variableType': data['variable']
                    })

                # Process different question response types
                if data['optionType'] == 'Buttons':
                    base_node["type"] = "Button"
                    if data.get('med_id'):
                        base_node["mediaID"] = data['med_id']
                    
                    nodes.append(base_node)
                    parent_id = current_id
                    current_id += 1
                    adjList.append([])  # Initialize adjacency list for parent

                    # Create child nodes for each button option
                    for option in data['options']:
                        btn_node = {
                            "id": current_id,
                            "body": option or "Choose Option:",
                            "type": "button_element"
                        }
                        nodes.append(btn_node)
                        adjList.append([])
                        adjList[parent_id].append(current_id)
                        current_id += 1
                
                elif data['optionType'] == 'Text':
                    base_node["type"] = "Text"
                    if data.get('med_id'):
                        base_node["mediaID"] = data['med_id']
                    nodes.append(base_node)
                    adjList.append([])
                    current_id += 1

                elif data['optionType'] == 'Lists':
                    base_node["type"] = "List"
                    nodes.append(base_node)
                    if data.get('listTitle'):
                        base_node["listTitle"] = data['listTitle']
                    parent_id = current_id
                    current_id += 1
                    adjList.append([])

                    # Create list item nodes
                    for option in data['options']:
                        list_node = {
                            "id": current_id,
                            "body": option or "Choose Option:",
                            "type": "list_element"
                        }
                        nodes.append(list_node)
                        adjList.append([])
                        adjList[parent_id].append(current_id)
                        current_id += 1

            # Handle Message Nodes
            elif node_block['type'] == 'sendMessage':
                data = node_block['data']
                msg_node = {
                    "oldIndex": node_block["id"],
                    "id": current_id,
                }

                delay = data.get('delay')
                if delay:
                    msg_node['delay'] = delay

                content = data['fields']['content']
                msg_type = data["fields"]['type']

                # Process different media types
                if msg_type == "text":
                    msg_node.update({
                        "type": "string",
                        "body": content['text']
                    })
                elif msg_type == "Image":
                    msg_node.update({
                        "type": "image",
                        "body": {"caption": content["caption"], "id": content["med_id"]}
                    })
                    # Add localized captions
                    for key, value in content.items():
                        if key.startswith('caption') and '_' in key:  # Avoid overwriting the 'text' key
                            language = key.split('_')[-1]  # Get language code (hi, mr, etc.)
                            msg_node['body'][f'caption_{language}'] = value

                elif msg_type == "Location":
                    msg_node["type"] = "location"
                    msg_node["body"] = {
                        "latitude": content["latitude"],
                        "longitude": content["longitude"],
                        "name": content["loc_name"],
                        "address": content["address"]
                    }
                elif msg_type == "Audio":
                    msg_node["type"] = "audio"
                    msg_node["body"] = {"audioID" : content["audioID"]}

                elif msg_type == "Video":
                    msg_node["type"] = "video"
                    msg_node["body"] = {"videoID" : content["videoID"]}
                
                nodes.append(msg_node)
                adjList.append([])
                current_id += 1

            elif node_block['type'] == 'setCondition':
                data = node_block['data']
                cond_node = {
                    "oldIndex": node_block["id"],
                    "id": current_id,
                    "body": data['condition'],
                    "type": "Button"
                }

                # Add optional delay and localized conditions
                for key, value in data.items():
                        if key.startswith('condition') and '_' in key:  # Avoid overwriting the 'text' key
                            language = key.split('_')[-1]  # Get language code (hi, mr, etc.)
                            cond_node[f'body_{language}'] = value

                delay = data.get('delay')
                if delay:
                    cond_node['delay'] = delay
                
                nodes.append(cond_node)
                adjList.append([])
                parent_id = current_id
                current_id += 1

                node = {
                    "id": id,
                    "body": "Yes",
                    "type": "button_element"
                }
                
                for choice in ["Yes", "No"]:
                    choice_node = {
                        "id": current_id,
                        "body": choice,
                        "type": "button_element"
                    }
                    nodes.append(choice_node)
                    adjList.append([])
                    adjList[parent_id].append(current_id)
                    current_id += 1

            elif node_block['type'] == 'ai':
                data = node_block['data']
                ai_node = {
                    "oldIndex": node_block["id"],
                    "id": current_id,
                    "type": "AI",
                    "body": data['label']
                }
                delay = data.get('delay')
                if delay:
                    ai_node['delay'] = delay
                
                nodes.append(ai_node)
                adjList.append([])
                current_id += 1

            elif node_block['type'] == 'product':
                data = node_block['data']
                product_node = {
                    "oldIndex": node_block['id'],
                    "id": current_id,
                    "type": "product",
                    "catalog_id": catalog_id,
                    "product": data['product_ids']
                }

                delay = data.get('delay')
                if delay:
                    product_node['delay'] = delay

                product_node['body'] = data.get('body', 'Your Catalog')
                product_node['footer'] = data.get('footer', 'Placing an order is subject to the availability of items.')
                product_node['header'] = data.get('head', 'Your Catalog')
                product_node['section_title'] = data.get('section_title', 'Item')
                nodes.append(product_node)
                adjList.append([])
                current_id += 1

            elif node_block['type'] == 'api':
                data = node_block['data']
                api_node = {
                    "oldIndex": node_block['id'],
                    "id": current_id,
                    "type": "api",
                }
                api_node['api'] = {
                    "method": data['method'],
                    "headers": data.get('headers', ''),
                    "endpoint": data['endpoint'],
                    "variable": data['variable']
                }
                delay = data.get('delay')
                if delay:
                    api_node['delay'] = delay

                nodes.append(api_node)
                adjList.append([])
                current_id += 1

            elif node_block['type'] == 'customint':
                data = node_block['data']
                customint_node = {
                    "oldIndex": node_block["id"],
                    "id": current_id,
                    "type": "customint",
                    "body": data['uniqueId']
                }
                nodes.append(customint_node)
                adjList.append([])
                current_id += 1
            elif node_block['type'] == 'flowjson':
                data = node_block['data']
                flow_json = {
                    "oldIndex": node_block["id"],
                    "id": current_id,
                    "type": "flowjson",
                    "flowName": data.get('flowName', ''),
                    "header": data.get('header', ''),
                    "body": data.get('body', ''),
                    "footer": data.get('footer', ''),  
                    "cta": data.get('cta', '')
                }
                nodes.append(flow_json)
                adjList.append([])
                current_id += 1

        # Process edges to build adjacency list
        startNode = None
        for edge in edges:
            # Identify start node
            if edge['source'] == "start":
                startNodeIndex = int(edge['target'])
                print("start node index: ", startNodeIndex)
                for node in nodes:
                    if 'oldIndex' in node:
                        if int(node['oldIndex']) == startNodeIndex:
                            startNode = int(node['id'])

            # Build node connections
            else:
                source = int(edge['source'])
                target = int(edge['target'])

                # Handle conditional branches
                suffix = 0
                sourcehandle = edge['sourceHandle']
                if sourcehandle not in [None, "text"]:
                    if sourcehandle == "true":
                        suffix += 1
                    elif sourcehandle == "false":
                        suffix += 2
                    else:
                        suffix += int(sourcehandle[-1]) + 1
                
                # Map original IDs to new sequential IDs
                for node in nodes:
                    if 'oldIndex' in node:
                        if int(node['oldIndex']) == source:
                            print("source")
                            n_source = int(node['id']) + suffix
                        if int(node['oldIndex']) == target:
                            print("target")
                            n_target = int(node['id'])
                print(f"source: {source}, target: {target}")
                adjList[n_source].append(n_target)

        # Cleanup temporary IDs
        for node in nodes:
            node.pop('oldIndex', None)
        print(f"fields: {fields}, start: {startNode}")

        return nodes, adjList, startNode, fields

    except Exception as e:
        print(f"An error occurred in convert flow: {e}")
        return None, None
